"""Procedural synthetic living room used by the mock pipeline, tests, and the
committed demo asset.

The scene must read instantly as a *room*: wood-plank floor with a rug and a
sun patch, plaster walls with ambient occlusion, a bright window, a door,
framed pictures, a sofa with cushions, a coffee table, a plant, and a floor
lamp. Surfaces are sampled as dense, small, surface-aligned gaussians so they
render crisp rather than blobby.

Deterministic for a given seed. Coordinates: +Y up, floor at y=0, room
centered on the origin — 5.0m (x) x 4.0m (z), 2.6m ceilings.
"""

from __future__ import annotations

import numpy as np

from .splat_format import SplatCloud

X = 2.5  # half width
Z = 2.0  # half depth
H = 2.6  # ceiling height

BASE_TOTAL = 45000  # reference splat count the default spacings produce

# Window on the back wall (z = -Z)
WIN_X0, WIN_X1, WIN_Y0, WIN_Y1 = -0.75, 0.75, 0.95, 2.15
# Door on the right wall (x = +X)
DOOR_Z0, DOOR_Z1, DOOR_H = 0.55, 1.45, 2.05


class _Builder:
    def __init__(self, rng: np.random.Generator, density: float):
        self.rng = rng
        self.density = max(density, 0.05)
        self.points: list[np.ndarray] = []
        self.sigmas: list[np.ndarray] = []
        self.colors: list[np.ndarray] = []
        self.alphas: list[np.ndarray] = []

    def _push(self, pos: np.ndarray, sig: np.ndarray, rgb: np.ndarray, alpha=None) -> None:
        self.points.append(pos.astype(np.float32))
        self.sigmas.append(sig.astype(np.float32))
        self.colors.append(np.clip(rgb, 0, 255).astype(np.float32))
        if alpha is None:
            alpha = np.full(len(pos), 255.0)
        self.alphas.append(np.clip(alpha, 0, 255).astype(np.float32))

    # ── primitives ────────────────────────────────────────────────────────

    def _grid(self, len_u: float, len_v: float, spacing: float):
        spacing = spacing / self.density
        nu = max(int(round(len_u / spacing)), 1)
        nv = max(int(round(len_v / spacing)), 1)
        s, t = np.meshgrid(
            (np.arange(nu) + 0.5) / nu,
            (np.arange(nv) + 0.5) / nv,
            indexing="ij",
        )
        s = s.ravel() + self.rng.normal(0, 0.25 / nu, nu * nv)
        t = t.ravel() + self.rng.normal(0, 0.25 / nv, nu * nv)
        return np.clip(s, 0, 1), np.clip(t, 0, 1)

    def surface(self, origin, u_axis, v_axis, spacing, color_fn, sigma, mask=None):
        """Rectangle origin + s*u + t*v with per-point color_fn(s, t, pos)."""
        origin_v = np.asarray(origin, np.float32)
        u = np.asarray(u_axis, np.float32)
        v = np.asarray(v_axis, np.float32)
        s, t = self._grid(np.linalg.norm(u), np.linalg.norm(v), spacing)
        pos = origin_v + s[:, None] * u + t[:, None] * v
        if mask is not None:
            keep = mask(s, t, pos)
            s, t, pos = s[keep], t[keep], pos[keep]
        if len(pos) == 0:
            return
        normal = np.cross(u, v)
        normal /= np.linalg.norm(normal)
        sig = np.full((len(pos), 3), sigma, np.float32)
        sig = sig * (1.0 - np.abs(normal)) + 0.012 * np.abs(normal)
        self._push(pos, sig, color_fn(s, t, pos))

    def box(self, center, size, color, spacing=0.035, sigma=0.026, faces="all", shade=0.06):
        cx, cy, cz = center
        sx, sy, sz = size
        base = np.asarray(color, np.float32)
        x0, x1, y0, y1, z0, z1 = cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, cz - sz / 2, cz + sz / 2
        # face: (origin, u, v, brightness) — simple fake lighting per face
        all_faces = {
            "top": ((x0, y1, z0), (sx, 0, 0), (0, 0, sz), 1.05),
            "bottom": ((x0, y0, z0), (sx, 0, 0), (0, 0, sz), 0.7),
            "front": ((x0, y0, z1), (sx, 0, 0), (0, sy, 0), 1.0),
            "back": ((x0, y0, z0), (sx, 0, 0), (0, sy, 0), 0.85),
            "left": ((x0, y0, z0), (0, 0, sz), (0, sy, 0), 0.9),
            "right": ((x1, y0, z0), (0, 0, sz), (0, sy, 0), 0.95),
        }
        wanted = all_faces.keys() if faces == "all" else faces
        for name in wanted:
            origin, u, v, lum = all_faces[name]

            def color_fn(s, t, pos, lum=lum):
                noise = self.rng.normal(1.0, shade, (len(s), 1))
                return base * lum * noise

            self.surface(origin, u, v, spacing, color_fn, sigma)

    def ellipsoid(self, center, radii, color, count=220, sigma=0.03, shade=0.07, lit_axis=1):
        """Surface-sampled ellipsoid with brighter top for a soft-lit look."""
        count = max(int(count * self.density**2), 12)
        d = self.rng.normal(0, 1, (count, 3))
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        pos = np.asarray(center, np.float32) + d * np.asarray(radii, np.float32)
        lum = 0.85 + 0.25 * (d[:, lit_axis] * 0.5 + 0.5)
        rgb = np.asarray(color, np.float32) * lum[:, None]
        rgb = rgb * self.rng.normal(1.0, shade, (count, 1))
        self._push(pos, np.full((count, 3), sigma, np.float32), rgb)

    def cylinder(self, base_center, radius, height, color, spacing=0.03, sigma=0.022, taper=1.0):
        cx, cy, cz = base_center
        spacing = spacing / self.density
        rows = max(int(height / spacing), 1)
        base = np.asarray(color, np.float32)
        pts, cols = [], []
        for i in range(rows):
            y = cy + (i + 0.5) / rows * height
            r = radius * (1 + (taper - 1) * i / max(rows - 1, 1))
            n = max(int(2 * np.pi * r / spacing), 6)
            ang = self.rng.uniform(0, 2 * np.pi) + np.linspace(0, 2 * np.pi, n, endpoint=False)
            pts.append(np.stack([cx + r * np.cos(ang), np.full(n, y), cz + r * np.sin(ang)], 1))
            lum = 0.8 + 0.4 * (np.cos(ang - 0.8) * 0.5 + 0.5)  # fake side lighting
            cols.append(base * lum[:, None])
        pos = np.concatenate(pts).astype(np.float32)
        rgb = np.concatenate(cols) * self.rng.normal(1.0, 0.05, (len(pos), 1))
        self._push(pos, np.full((len(pos), 3), sigma, np.float32), rgb)

    def contact_shadow(self, center_xz, radii_xz, strength=130.0) -> None:
        """Soft dark ellipse on the floor that visually grounds furniture."""
        cx, cz = center_xz
        rx, rz = radii_xz
        count = max(int(900 * rx * rz * self.density**2), 20)
        u = self.rng.uniform(-1, 1, (count, 2))
        u = u[np.sum(u * u, 1) <= 1.0]
        r2 = np.sum(u * u, 1)
        pos = np.stack(
            [cx + u[:, 0] * rx, np.full(len(u), 0.035, np.float32), cz + u[:, 1] * rz], 1
        )
        alpha = strength * np.exp(-2.6 * r2)
        rgb = np.full((len(u), 3), 30.0)
        self._push(pos, np.full((len(u), 3), 0.05, np.float32), rgb, alpha)

    # ── result ────────────────────────────────────────────────────────────

    def to_cloud(self) -> SplatCloud:
        pos = np.concatenate(self.points)
        sig = np.concatenate(self.sigmas)
        rgb = np.concatenate(self.colors)
        alpha = np.concatenate(self.alphas)
        n = len(pos)
        colors = np.concatenate([rgb, alpha[:, None]], 1).astype(np.uint8)
        rot = np.concatenate([np.ones((n, 1), np.float32), np.zeros((n, 3), np.float32)], 1)
        return SplatCloud(positions=pos, scales=sig, colors=colors, rotations=rot)


def _wall_ao(y: np.ndarray, along: np.ndarray, length: float) -> np.ndarray:
    """Ambient-occlusion factor for wall points: darker near floor, ceiling
    and vertical corners. `along` is the position along the wall in meters."""
    ao = np.ones_like(y)
    ao *= 0.86 + 0.14 * np.clip(y / 0.5, 0, 1)  # floor contact shadow
    ao *= 0.93 + 0.07 * np.clip((H - y) / 0.45, 0, 1)  # ceiling corner
    edge = np.minimum(along, length - along)
    ao *= 0.88 + 0.12 * np.clip(edge / 0.45, 0, 1)  # vertical corners
    return ao


def synthetic_room_splats(total: int = BASE_TOTAL, seed: int = 42) -> SplatCloud:
    """Build the demo living room as ~``total`` gaussians."""
    rng = np.random.default_rng(seed)
    b = _Builder(rng, density=float(np.sqrt(total / BASE_TOTAL)))

    _floor(b)
    _ceiling(b)
    _walls(b)
    _window(b)
    _door(b)
    _pictures(b)
    _sofa(b)
    _coffee_table(b)
    _plant(b)
    _lamp(b)

    # contact shadows ground the furniture on the floor
    b.contact_shadow((-2.1, 0.35), (0.62, 1.12), strength=120)  # sofa
    b.contact_shadow((0.45, 0.35), (0.52, 0.52), strength=110)  # coffee table
    b.contact_shadow((1.95, -1.5), (0.3, 0.3), strength=120)  # plant
    b.contact_shadow((-1.6, -1.55), (0.22, 0.22), strength=100)  # lamp
    return b.to_cloud()


# ── scene elements ─────────────────────────────────────────────────────────

def _floor(b: _Builder) -> None:
    plank_w = 0.14

    def color_fn(s, t, pos):
        x, z = pos[:, 0], pos[:, 2]
        plank = np.floor((z + Z) / plank_w)
        base = np.stack([np.full_like(x, 176.0), np.full_like(x, 140.0), np.full_like(x, 99.0)], 1)
        # per-plank tone + seams between planks + subtle grain along x
        tone = 0.9 + 0.18 * _hash01(plank)
        seam = 1.0 - 0.28 * (np.abs(((z + Z) % plank_w) - plank_w / 2) > plank_w * 0.44)
        grain = 1.0 + 0.05 * np.sin(x * 23.0 + plank * 7.0)
        lum = tone * seam * grain
        # warm sun patch cast through the window
        in_sun = (z < -0.2) & (z > -1.9) & (np.abs(x - 0.15 * (z + 1.9)) < 0.85)
        lum = lum * np.where(in_sun, 1.22, 1.0)
        rgb = base * lum[:, None]
        rgb[in_sun, 0] *= 1.04  # warm tint
        return rgb * b.rng.normal(1.0, 0.03, (len(s), 1))

    b.surface((-X, 0.0, -Z), (2 * X, 0, 0), (0, 0, 2 * Z), 0.045, color_fn, sigma=0.032)
    _rug(b)


def _rug(b: _Builder) -> None:
    cx, cz, rx, rz = -0.55, 0.35, 1.25, 0.95

    def mask(s, t, pos):
        return ((pos[:, 0] - cx) / rx) ** 2 + ((pos[:, 2] - cz) / rz) ** 2 <= 1.0

    def color_fn(s, t, pos):
        r2 = ((pos[:, 0] - cx) / rx) ** 2 + ((pos[:, 2] - cz) / rz) ** 2
        border = r2 > 0.72
        base = np.where(border[:, None], [[152.0, 88.0, 70.0]], [[198.0, 122.0, 96.0]])
        weave = 1.0 + 0.06 * np.sin(pos[:, 0] * 40) * np.sin(pos[:, 2] * 40)
        return base * weave[:, None] * b.rng.normal(1.0, 0.04, (len(s), 1))

    b.surface(
        (cx - rx, 0.02, cz - rz), (2 * rx, 0, 0), (0, 0, 2 * rz), 0.04, color_fn, 0.03, mask=mask
    )


def _ceiling(b: _Builder) -> None:
    def color_fn(s, t, pos):
        edge = np.minimum.reduce(
            [pos[:, 0] + X, X - pos[:, 0], pos[:, 2] + Z, Z - pos[:, 2]]
        )
        ao = 0.88 + 0.12 * np.clip(edge / 0.5, 0, 1)
        return np.array([[242.0, 240.0, 234.0]]) * ao[:, None] * b.rng.normal(
            1.0, 0.02, (len(s), 1)
        )

    b.surface((-X, H, -Z), (2 * X, 0, 0), (0, 0, 2 * Z), 0.075, color_fn, sigma=0.055)


def _walls(b: _Builder) -> None:
    plaster = np.array([234.0, 228.0, 216.0])
    accent = np.array([158.0, 172.0, 158.0])  # sage accent behind the window

    def wall(origin, u, v, length, base, mask=None):
        def color_fn(s, t, pos):
            ao = _wall_ao(pos[:, 1], s * length, length)
            return base[None, :] * ao[:, None] * b.rng.normal(1.0, 0.025, (len(s), 1))

        b.surface(origin, u, v, 0.055, color_fn, sigma=0.04, mask=mask)

    def outside_window(s, t, pos):
        return ~(
            (pos[:, 0] > WIN_X0 - 0.06) & (pos[:, 0] < WIN_X1 + 0.06)
            & (pos[:, 1] > WIN_Y0 - 0.06) & (pos[:, 1] < WIN_Y1 + 0.06)
        )

    def outside_door(s, t, pos):
        return ~(
            (pos[:, 2] > DOOR_Z0 - 0.05) & (pos[:, 2] < DOOR_Z1 + 0.05) & (pos[:, 1] < DOOR_H + 0.05)
        )

    wall((-X, 0, -Z), (2 * X, 0, 0), (0, H, 0), 2 * X, accent, mask=outside_window)  # back
    wall((-X, 0, Z), (2 * X, 0, 0), (0, H, 0), 2 * X, plaster)  # front (behind camera)
    wall((-X, 0, -Z), (0, 0, 2 * Z), (0, H, 0), 2 * Z, plaster)  # left
    wall((X, 0, -Z), (0, 0, 2 * Z), (0, H, 0), 2 * Z, plaster, mask=outside_door)  # right

    # baseboards — white skirting sells the wall/floor junction
    def white(s, t, pos):
        return np.array([[246.0, 244.0, 238.0]]) * b.rng.normal(1.0, 0.02, (len(s), 1))

    bb = 0.09
    b.surface((-X, 0, -Z + 0.012), (2 * X, 0, 0), (0, bb, 0), 0.03, white, 0.02)
    b.surface((-X, 0, Z - 0.012), (2 * X, 0, 0), (0, bb, 0), 0.03, white, 0.02)
    b.surface((-X + 0.012, 0, -Z), (0, 0, 2 * Z), (0, bb, 0), 0.03, white, 0.02)

    def bb_outside_door(s, t, pos):
        return (pos[:, 2] < DOOR_Z0) | (pos[:, 2] > DOOR_Z1)

    b.surface(
        (X - 0.012, 0, -Z), (0, 0, 2 * Z), (0, bb, 0), 0.03, white, 0.02, mask=bb_outside_door
    )


def _window(b: _Builder) -> None:
    zw = -Z + 0.02
    w, h = WIN_X1 - WIN_X0, WIN_Y1 - WIN_Y0

    def glass(s, t, pos):
        # sky gradient with a soft sun glow in the upper-left pane
        top = np.array([158.0, 202.0, 240.0])
        bottom = np.array([224.0, 236.0, 246.0])
        rgb = bottom[None, :] + (top - bottom)[None, :] * t[:, None]
        glow = np.exp(-(((s - 0.3) / 0.28) ** 2 + ((t - 0.75) / 0.3) ** 2))
        return rgb + glow[:, None] * np.array([[70.0, 45.0, 10.0]])

    b.surface((WIN_X0, WIN_Y0, zw), (w, 0, 0), (0, h, 0), 0.045, glass, sigma=0.035)

    def frame(s, t, pos):
        return np.array([[250.0, 250.0, 248.0]]) * b.rng.normal(1.0, 0.02, (len(s), 1))

    f = 0.06
    zf = zw + 0.015
    b.surface((WIN_X0 - f, WIN_Y0 - f, zf), (w + 2 * f, 0, 0), (0, f, 0), 0.025, frame, 0.018)
    b.surface((WIN_X0 - f, WIN_Y1, zf), (w + 2 * f, 0, 0), (0, f, 0), 0.025, frame, 0.018)
    b.surface((WIN_X0 - f, WIN_Y0, zf), (f, 0, 0), (0, h, 0), 0.025, frame, 0.018)
    b.surface((WIN_X1, WIN_Y0, zf), (f, 0, 0), (0, h, 0), 0.025, frame, 0.018)
    # mullions (cross bars)
    b.surface((WIN_X0, (WIN_Y0 + WIN_Y1) / 2 - 0.02, zf), (w, 0, 0), (0, 0.04, 0), 0.02, frame, 0.014)
    b.surface(((WIN_X0 + WIN_X1) / 2 - 0.02, WIN_Y0, zf), (0.04, 0, 0), (0, h, 0), 0.02, frame, 0.014)


def _door(b: _Builder) -> None:
    xd = X - 0.02
    w = DOOR_Z1 - DOOR_Z0

    def leaf(s, t, pos):
        # two recessed panels
        panel = (
            ((s > 0.15) & (s < 0.85) & (t > 0.08) & (t < 0.45))
            | ((s > 0.15) & (s < 0.85) & (t > 0.55) & (t < 0.92))
        )
        base = np.where(panel[:, None], [[196.0, 190.0, 180.0]], [[212.0, 206.0, 196.0]])
        return base * b.rng.normal(1.0, 0.025, (len(s), 1))

    b.surface((xd, 0, DOOR_Z0), (0, 0, w), (0, DOOR_H, 0), 0.04, leaf, sigma=0.03)

    def trim(s, t, pos):
        return np.array([[246.0, 244.0, 238.0]]) * b.rng.normal(1.0, 0.02, (len(s), 1))

    f = 0.07
    b.surface((xd - 0.005, 0, DOOR_Z0 - f), (0, 0, f), (0, DOOR_H + f, 0), 0.03, trim, 0.02)
    b.surface((xd - 0.005, 0, DOOR_Z1), (0, 0, f), (0, DOOR_H + f, 0), 0.03, trim, 0.02)
    b.surface((xd - 0.005, DOOR_H, DOOR_Z0 - f), (0, 0, w + 2 * f), (0, f, 0), 0.03, trim, 0.02)
    b.ellipsoid((xd - 0.05, 1.02, DOOR_Z1 - 0.12), (0.028, 0.028, 0.028), (196, 168, 110), count=40, sigma=0.016)


def _pictures(b: _Builder) -> None:
    def art_a(s, t, pos):  # muted sunset print on the left wall
        sky = np.array([226.0, 168.0, 120.0])
        sea = np.array([96.0, 118.0, 138.0])
        rgb = sea[None, :] + (sky - sea)[None, :] * np.clip(t[:, None] * 1.4 - 0.2, 0, 1)
        return rgb

    def art_b(s, t, pos):  # abstract green print on the back wall
        aa = np.array([210.0, 214.0, 198.0])
        bb_ = np.array([104.0, 128.0, 104.0])
        m = (np.sin(s * 9) * np.cos(t * 7) * 0.5 + 0.5)[:, None]
        return aa[None, :] + (bb_ - aa)[None, :] * m

    def frame(s, t, pos):
        return np.full((len(s), 3), 58.0)

    def picture(origin, u, v, art):
        b.surface(origin, u, v, 0.03, art, 0.022)
        un = np.asarray(u, np.float32)
        vn = np.asarray(v, np.float32)
        eu = un / np.linalg.norm(un)
        ev = vn / np.linalg.norm(vn)
        fw = 0.045
        o = np.asarray(origin, np.float32)
        b.surface(o - eu * fw - ev * fw, un + eu * 2 * fw, ev * fw, 0.02, frame, 0.014)
        b.surface(o + vn - eu * fw, un + eu * 2 * fw, ev * fw, 0.02, frame, 0.014)
        b.surface(o - eu * fw, eu * fw, vn, 0.02, frame, 0.014)
        b.surface(o + un, eu * fw, vn, 0.02, frame, 0.014)

    picture((-X + 0.03, 1.25, -0.2), (0, 0, 0.85), (0, 0.6, 0), art_a)
    picture((1.35, 1.35, -Z + 0.03), (0.7, 0, 0), (0, 0.5, 0), art_b)


def _sofa(b: _Builder) -> None:
    # against the left wall, facing the room center (+x)
    fabric = (98, 112, 136)
    seat = (112, 126, 150)
    x0 = -X + 0.35  # sofa center line x
    base_y = 0.18

    b.box(
        (x0, base_y + 0.14, 0.35), (0.85, 0.28, 1.9), fabric,
        spacing=0.026, sigma=0.03, shade=0.05,
        faces=("front", "right", "left", "top", "back"),
    )
    # backrest against the wall
    b.box((x0 - 0.32, 0.55, 0.35), (0.22, 0.75, 1.9), fabric, spacing=0.026, sigma=0.03, shade=0.05)
    # armrests
    b.box((x0, 0.42, 0.35 - 1.02), (0.85, 0.5, 0.22), fabric, spacing=0.026, sigma=0.03, shade=0.05)
    b.box((x0, 0.42, 0.35 + 1.02), (0.85, 0.5, 0.22), fabric, spacing=0.026, sigma=0.03, shade=0.05)
    # seat cushions
    b.ellipsoid((x0 + 0.06, 0.42, -0.12), (0.4, 0.09, 0.42), seat, count=1100, sigma=0.03, shade=0.05)
    b.ellipsoid((x0 + 0.06, 0.42, 0.82), (0.4, 0.09, 0.42), seat, count=1100, sigma=0.03, shade=0.05)
    # back cushions
    b.ellipsoid((x0 - 0.16, 0.78, -0.12), (0.11, 0.26, 0.4), (104, 118, 142), count=900, sigma=0.03, shade=0.05)
    b.ellipsoid((x0 - 0.16, 0.78, 0.82), (0.11, 0.26, 0.4), (104, 118, 142), count=900, sigma=0.03, shade=0.05)
    # accent pillows
    b.ellipsoid((x0 - 0.05, 0.62, 0.35), (0.16, 0.17, 0.17), (204, 164, 118), count=560, sigma=0.026)
    b.ellipsoid((x0 - 0.02, 0.6, -0.6), (0.15, 0.16, 0.16), (156, 168, 146), count=500, sigma=0.026)
    # wooden legs
    for dz in (-0.8, 0.8):
        for dx in (-0.3, 0.3):
            b.cylinder((x0 + dx, 0.0, 0.35 + dz), 0.03, base_y, (92, 72, 54), spacing=0.025)


def _coffee_table(b: _Builder) -> None:
    cx, cz, top_y, r = 0.45, 0.35, 0.42, 0.42

    def top(s, t, pos):
        ring = 1.0 + 0.07 * np.sin(np.hypot(pos[:, 0] - cx, pos[:, 2] - cz) * 55)
        return np.array([[132.0, 100.0, 70.0]]) * ring[:, None] * b.rng.normal(
            1.0, 0.03, (len(s), 1)
        )

    def disk(s, t, pos):
        return (pos[:, 0] - cx) ** 2 + (pos[:, 2] - cz) ** 2 <= r * r

    b.surface((cx - r, top_y, cz - r), (2 * r, 0, 0), (0, 0, 2 * r), 0.028, top, 0.02, mask=disk)
    # rim
    b.cylinder((cx, top_y - 0.035, cz), r, 0.035, (110, 82, 58), spacing=0.025)
    for ang in (0.6, 2.1, 3.7, 5.2):
        b.cylinder(
            (cx + 0.3 * np.cos(ang), 0.0, cz + 0.3 * np.sin(ang)),
            0.025, top_y - 0.03, (74, 58, 44), spacing=0.025,
        )
    # a couple of books on the table
    b.box((cx - 0.1, top_y + 0.025, cz + 0.05), (0.26, 0.045, 0.19), (168, 84, 72), spacing=0.022, sigma=0.016)
    b.box((cx - 0.07, top_y + 0.06, cz + 0.02), (0.22, 0.03, 0.16), (86, 104, 128), spacing=0.022, sigma=0.016)


def _plant(b: _Builder) -> None:
    px, pz = 1.95, -1.5
    b.cylinder((px, 0.0, pz), 0.16, 0.34, (172, 112, 88), spacing=0.024, taper=0.82)  # pot
    b.cylinder((px, 0.3, pz), 0.025, 0.75, (98, 78, 58), spacing=0.028)  # trunk
    rng = b.rng
    for _ in range(int(26 * max(b.density, 0.3))):
        ang = rng.uniform(0, 2 * np.pi)
        rad = rng.uniform(0.05, 0.38)
        y = 1.0 + rng.uniform(0, 0.75) - rad * 0.4
        green = np.array([70.0, 116.0, 68.0]) * rng.uniform(0.82, 1.22)
        b.ellipsoid(
            (px + rad * np.cos(ang), y, pz + rad * np.sin(ang)),
            (0.14, 0.1, 0.14), tuple(green), count=90, sigma=0.026, shade=0.12,
        )


def _lamp(b: _Builder) -> None:
    lx, lz = -1.6, -1.55
    b.cylinder((lx, 0.0, lz), 0.14, 0.03, (60, 60, 62), spacing=0.022)  # base
    b.cylinder((lx, 0.03, lz), 0.018, 1.35, (70, 70, 72), spacing=0.028)  # pole
    # glowing warm shade
    b.cylinder((lx, 1.38, lz), 0.16, 0.24, (252, 228, 176), spacing=0.022, taper=0.8)
    b.ellipsoid((lx, 1.5, lz), (0.12, 0.1, 0.12), (255, 240, 200), count=160, sigma=0.035)


def _hash01(v: np.ndarray) -> np.ndarray:
    """Deterministic pseudo-random in [0,1) per integer input."""
    return (np.sin(v * 127.1 + 311.7) * 43758.5453) % 1.0
