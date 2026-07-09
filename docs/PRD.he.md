# מסמך איפיון: פלטפורמת SpatialScan (גרסת MVP)

> English version: [PRD.en.md](PRD.en.md) · ארכיטקטורה: [ARCHITECTURE.md](ARCHITECTURE.md) · צוות וכישורים: [TEAM_SKILLS.md](TEAM_SKILLS.md)

## 1. תמצית המוצר (Product Vision)

SpatialScan היא פלטפורמת SaaS שהופכת סרטון וידאו סלולרי רגיל (עד 45 שניות) למודל תלת-ממדי פוטו-ריאליסטי — סיור וירטואלי שאפשר "ללכת" בתוכו בחופשיות בדפדפן, ללא אפליקציה וללא חומרה ייעודית.

**היתרון התחרותי מול Matterport:**

| | Matterport | SpatialScan |
|---|---|---|
| חומרה | מצלמת 360° ייעודית (אלפי דולרים) | כל סמארטפון |
| טכנולוגיה | Photogrammetry / מצלמות עומק | 3D Gaussian Splatting (3DGS) |
| עלות תשתית בזמן המתנה | שרתים קבועים | **אפס** — Serverless GPU שנרדם |
| זמן עד תוצאה | שעות (סריקה + עיבוד) | דקות ספורות |
| צפייה | אפליקציה / viewer כבד | דפדפן, טעינה פרוגרסיבית |

## 2. אסטרטגיה כלכלית (Free-Tier → Serverless)

המערכת מתוכננת כך שאותו קוד עיבוד רץ בשלוש סביבות, והמעבר ביניהן הוא משתני סביבה בלבד:

1. **שלב הפיתוח (0 ₪):** מצב `mock` — הפייפליין מייצר סצנה סינתטית, כל הזרימה נבדקת על כל לפטופ בלי GPU.
2. **שלב הטסטים (0 ₪):** Google Colab עם GPU T4 חינמי (דרך ה-notebook שבריפו), או VM ב-GCP עם קרדיט הניסיון של $300.
   ⚠️ **הערה חשובה:** כלי בשם `@googlecolab/cli` עם פקודות כמו `colab new --gpu T4` **אינו קיים**. המסלול האמיתי מתועד ב-[FREE_TIER_TESTING.md](FREE_TIER_TESTING.md) — notebook שמשכפל את הריפו ומריץ את ה-CLI של ה-worker על ה-GPU של Colab.
3. **שלב הפרודקשן (הכי זול):** RunPod Serverless — קונטיינר GPU (למשל RTX 4090) מתעורר רק כשיש משימה בתור, מחויב לפי שניות עבודה בלבד, ונכבה מיד. אחסון ב-Cloudflare R2 (ללא עלויות egress).

## 3. ארכיטקטורת המערכת

```
[ דפדפן מובייל (PWA) ] ──(MP4 + metadata JSON)──▶ [ API Gateway (FastAPI) ]
                                                        │
                                          תור משימות (Redis) ─── פיתוח
                                          RunPod Serverless ─── פרודקשן
                                                        │
[ דפדפן: סיור 3D ] ◀──(.splat)── [ Worker: ffmpeg → COLMAP → 3DGS → export ]
```

- **אחסון:** Object Storage תואם S3 (Cloudflare R2 בפרודקשן, MinIO/דיסק מקומי בפיתוח). הוידאו הגולמי, קובץ ה-`.splat` וה-`manifest.json` נשמרים תחת `jobs/{job_id}/`.
- **אבטחת ה-Worker:** ה-worker מקבל **presigned URLs** בלבד (GET לוידאו, PUT לתוצאות) — קונטיינר ה-GPU לא מחזיק credentials לאחסון.
- **מצב משימה:** Redis hash per-job עם TTL של 7 ימים; ה-manifest באחסון הוא המקור העמיד.

## 4. דרישות פונקציונליות (MVP)

### 4.1 מודול הלקוח (Web/PWA)

| דרישה | מימוש |
|---|---|
| צילום/בחירת וידאו | `<input capture="environment">` — מצלמה אחורית או קובץ קיים |
| Guardrail משך | עד **45 שניות**; נבדק בצד הלקוח לפני העלאה ושוב בצד השרת |
| חילוץ מטא-דטה | משך + רזולוציה מ-`loadedmetadata`; FPS מוערך דרך `requestVideoFrameCallback` (הדפדפן לא חושף FPS — best-effort, נשלח `null` אם נכשל) |
| מעקב התקדמות | polling כל 2 שניות; stepper של חמשת השלבים |
| שיתוף | לינק לסיור דרך Web Share API / העתקה |

### 4.2 מנוע העיבוד (Worker)

| שלב | כלי | פרמטרים |
|---|---|---|
| א. חילוץ פריימים | ffmpeg | ~3 פריימים לשנייה (`FRAMES_PER_SECOND`) |
| ב. שחזור מצלמה | COLMAP (דרך `ns-process-data`) | Structure-from-Motion → `transforms.json` |
| ג. אימון 3DGS | nerfstudio `splatfacto` (מבוסס gsplat) | ~5,000 איטרציות (`TRAIN_ITERATIONS`) — כ-3 דקות על GPU מודרני |
| ד. ייצוא | ממיר PLY→splat פנימי | פורמט `.splat` (antimatter15, 32 bytes/splat); pruning לפי opacity עד תקציב **40MB** (`SPLAT_MAX_MB`) |

**עיקרון מבני:** פייפליין אחד (`run_pipeline()`) עם שלושה entrypoints — תור Redis (פיתוח), RunPod handler (פרודקשן), CLI (Colab/GCP). כל שלב קיים בגרסת `real` ובגרסת `mock`, ו-`PIPELINE_MODE=auto` בוחר אוטומטית לפי הכלים המותקנים.

### 4.3 מציג הסיורים (Web Viewer)

- **רינדור:** Three.js + `@mkkellogg/gaussian-splats-3d`.
- **ניווט First-Person מותאם מגע:** גרירה = הסתכלות (yaw/pitch, מוגבל ±80°); הקשה = צעד קדימה בגובה עיניים קבוע; pinch = התקרבות; גלגלת בדסקטופ.
- **טעינה פרוגרסיבית:** המשתמש רואה את החלל מטושטש שמתחדד תוך 2-3 שניות (`progressiveLoad`).
- **ללא דרישות COOP/COEP:** `sharedMemoryForWorkers: false` — עובד מכל CDN סטטי.

## 5. דרישות לא-פונקציונליות

| מדד | יעד |
|---|---|
| זמן קצה-לקצה (העלאה → לינק) | **< 7 דקות** לחלל ממוצע |
| FPS במובייל (iOS Safari / Android Chrome) | **60 FPS** — קריטי למניעת בחילת תנועה. אמצעים: תקציב splats בייצוא, `devicePixelRatio` מוגבל ל-2, גובה עיניים קבוע |
| גודל קובץ סיור | < 40MB (בפועל סצנת MVP ≈ 5-15MB) |
| זמינות תוצאות | manifest + splat באחסון עמיד; Redis ניתן לאיבוד |

## 6. מחוץ לתחולת ה-MVP

חשבונות משתמשים ואימות, חיוב ומכסות, אפליקציה נייטיבית (שלב 2 — Flutter/RN מעל אותו API), חיבור רב-חדרים (stitching), עריכת סצנות, מדידות בתוך הסיור, תמיכה ב-offline.

## 7. מדדי הצלחה ל-MVP

1. משתמש שאינו טכני מפיק סיור מוצלח מסרטון ראשון ב->80% מהמקרים (בהנחיית ה-UI).
2. עלות עיבוד ממוצעת לסיור < $0.05 (RunPod 4090 ≈ $0.00019/שנייה × ~4 דקות).
3. זמן טעינת סיור עד אינטראקציה < 3 שניות ב-4G.
