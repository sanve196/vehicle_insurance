# ACC — AI Vehicle Insurance Platform

Built by **Applied Cloud Computing (ACC)** · AWS Premier Tier Services Partner

An AI-powered vehicle insurance underwriting platform demonstrating:

1. **Document verification** — OCR a registration document (RC book), extract key fields, and cross-check them against the application form data. Returns a per-field match table, document-type detection, and an overall confidence verdict.
2. **Vehicle inspection** — Accept a walk-around video, extract key frames, check capture quality (sharpness/brightness/vehicle-present), and produce a condition signal with an insurability recommendation.

> Every AI output is a **recommendation**. A human reviewer is expected to confirm or override before any underwriting decision.

## What is real vs. demo

| Capability | Status |
|---|---|
| OCR text extraction (Tesseract) | Real |
| Field extraction from RC text | Real (regex heuristics) |
| Form-vs-document match scoring | Real (fuzzy matching) |
| Document-type detection | Real (keyword heuristic) |
| Video frame extraction (OpenCV) | Real |
| Frame quality checks (blur/brightness) | Real |
| Damage detection / severity | **Demo heuristic** — replace with a trained CV model in production |

## Tech stack
- FastAPI + Uvicorn (Python 3.11)
- Tesseract OCR, OpenCV (headless), Pillow, RapidFuzz
- Vanilla HTML/CSS/JS frontend
- Docker (for reproducible deploy on Render)

## Run locally

### With Docker (recommended — matches production)
```bash
docker build -t autoverify .
docker run -p 8000:8000 autoverify
# open http://localhost:8000
```

### Without Docker
Install system packages first:
```bash
# macOS
brew install tesseract ffmpeg
# Ubuntu/Debian
sudo apt-get install tesseract-ocr ffmpeg libgl1
```
Then:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://localhost:8000
```

## API
- `GET /` — web UI
- `GET /health` — health check
- `POST /api/verify-document` — multipart: `document` (image) + form fields
- `POST /api/analyze-video` — multipart: `video` (mp4/mov)

## Deploy on Render
See the deployment steps shared separately, or use the included `render.yaml` blueprint.

## Project structure
```
app/
  main.py            # FastAPI routes
  services/
    ocr.py           # OCR + field extraction
    verify.py        # form-vs-doc matching + doc classification
    video.py         # frame extraction + quality + damage signal
  templates/index.html
  static/style.css, app.js
Dockerfile
render.yaml
requirements.txt
```
