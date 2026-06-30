"""AI-Based Vehicle Insurance — Demo API + UI."""
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from app.services.ocr import run_ocr, extract_fields
from app.services.verify import verify, classify_document
from app.services.video import analyze_video

app = FastAPI(title="AI Vehicle Insurance Demo")

BASE = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

MAX_IMAGE_MB = 10
MAX_VIDEO_MB = 50


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/verify-document")
async def verify_document(
    document: UploadFile = File(...),
    registration_number: str = Form(""),
    chassis_number: str = Form(""),
    engine_number: str = Form(""),
    owner_name: str = Form(""),
    fuel_type: str = Form(""),
):
    data = await document.read()
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        return JSONResponse({"error": f"Image exceeds {MAX_IMAGE_MB}MB."}, status_code=413)

    raw_text = run_ocr(data)
    doc_type = classify_document(raw_text)
    extracted = extract_fields(raw_text)
    form_data = {
        "registration_number": registration_number,
        "chassis_number": chassis_number,
        "engine_number": engine_number,
        "owner_name": owner_name,
        "fuel_type": fuel_type,
    }
    result = verify(form_data, extracted)
    return {
        "document_type": doc_type,
        "extracted_fields": extracted,
        "verification": result,
        "ocr_chars": len(raw_text),
    }


@app.post("/api/analyze-video")
async def analyze_video_endpoint(video: UploadFile = File(...)):
    data = await video.read()
    if len(data) > MAX_VIDEO_MB * 1024 * 1024:
        return JSONResponse({"error": f"Video exceeds {MAX_VIDEO_MB}MB."}, status_code=413)
    result = analyze_video(data)
    status = 400 if "error" in result else 200
    return JSONResponse(result, status_code=status)
