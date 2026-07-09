# Free-Tier GPU Testing Guide · מדריך בדיקות GPU בחינם

How to run the **real** pipeline (ffmpeg → COLMAP → 3DGS training → `.splat`) without paying for GPU time.

איך מריצים את הפייפליין **האמיתי** בלי לשלם על GPU.

---

## ⚠️ First, a correction · תיקון חשוב

Earlier planning material referenced an npm package **`@googlecolab/cli`** with commands like `colab new --gpu T4` and `colab exec`. **No such official tool exists** — Google Colab has no supported CLI for provisioning free GPUs from your terminal. Anything claiming otherwise will waste your time (or worse, is a typosquatted package — do not `npm install` it).

חומר תכנון מוקדם הזכיר כלי בשם `@googlecolab/cli` עם פקודות כמו `colab new --gpu T4`. **כלי כזה לא קיים.** ל-Colab אין CLI רשמי להקצאת GPU חינמי מהטרמינל. אל תתקינו חבילה בשם הזה — היא עלולה להיות זדונית.

The real free options are below, in order of convenience.

---

## Option A (recommended): Google Colab notebook — free T4 GPU

**What you get:** NVIDIA T4 (16GB VRAM), free tier, sessions up to a few hours — plenty for a 45-second video (~5–10 minutes of processing).

1. Open [Google Colab](https://colab.research.google.com) and upload [`notebooks/spatialscan_worker_colab.ipynb`](../notebooks/spatialscan_worker_colab.ipynb) (or open it straight from GitHub: File → Open notebook → GitHub → paste this repo).
2. Runtime → Change runtime type → **T4 GPU**.
3. Run the cells top to bottom. The notebook:
   - verifies the GPU (`nvidia-smi`),
   - installs COLMAP + ffmpeg (apt) and PyTorch + nerfstudio (pip),
   - clones this repository and installs `spatialscan_worker`,
   - lets you upload a short video you filmed,
   - runs `python -m spatialscan_worker.cli --video your.mp4 --out out/ --mode real`,
   - downloads the resulting `scene.splat` to your machine.
4. View the result locally: drop the file into `apps/web/public/`, run `npm run dev`, and open `/tour/sample` after replacing `sample.splat` (or use any online .splat viewer).

**Free-tier notes:** you may be disconnected at peak times; training at 5,000 iterations on a T4 takes ~5–8 minutes for a small room. Filming tips are in the notebook (slow lateral movement, overlap, good light).

## Option B: GCP $300 free-trial credit — a real VM you control

**What you get:** ~$300 / 90 days of credit. An `n1-standard-8` + T4 costs ≈ $0.55/hr (hundreds of processing hours), an L4 ≈ $0.87/hr.

```bash
# One-time: create the VM (adjust zone/quota as needed; GPU quota may need a request)
gcloud compute instances create spatialscan-dev \
  --zone=us-central1-a \
  --machine-type=n1-standard-8 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=pytorch-latest-gpu \
  --image-project=deeplearning-platform-release \
  --maintenance-policy=TERMINATE \
  --boot-disk-size=100GB

gcloud compute ssh spatialscan-dev --zone=us-central1-a

# On the VM:
sudo apt-get update && sudo apt-get install -y colmap ffmpeg
pip install nerfstudio
git clone https://github.com/Gilhzn/Parallax-AI.git && cd Parallax-AI
pip install -e services/worker
python -m spatialscan_worker.cli --video my_room.mp4 --out out/ --mode real
```

**⚠️ Stop the VM when idle** — `gcloud compute instances stop spatialscan-dev`. The credit burns while it runs. This is exactly the failure mode the production serverless design eliminates.

## Option C: RunPod — cheap by the second (not free, but near-free for tests)

A one-off RunPod **Pod** (not serverless) with an RTX 3090/4090 costs ~$0.2–0.4/hr billed per second. Use the worker Docker image:

```bash
docker build -t spatialscan-worker:gpu -f services/worker/Dockerfile services/worker
# push to a registry, start a RunPod pod from it, then inside:
python -m spatialscan_worker.cli --video my_room.mp4 --out out/ --mode real
```

This doubles as the dress rehearsal for the production serverless endpoint ([infra/runpod/endpoint.md](../infra/runpod/endpoint.md)).

---

## What to validate during free-tier testing · מה לבדוק בשלב הזה

| Check | Pass criteria |
|---|---|
| COLMAP pose recovery | >80% of frames registered on a normal room video |
| Training time @5,000 iters | ≤ 5 min on T4, ≤ 90s on 4090 |
| Export size | `scene.splat` < 40MB, loads in the web viewer |
| Visual quality | Recognizable, walkable room; no severe floaters |
| End-to-end wall time | < 10 min on T4 (target < 7 min on prod GPU) |

Record these per test video — they calibrate `TRAIN_ITERATIONS` / `FRAMES_PER_SECOND` defaults and the production GPU choice.
