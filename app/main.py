"""AI-Based Vehicle Insurance — Demo API + UI."""
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from app.services.ocr import run_ocr, extract_fields
from app.services.verify import verify, classify_document
from app.services.video import analyze_video
from app.services.photo import analyze_photos
from app.services.rc_lookup import lookup_vehicle
from app.services import db

app = FastAPI(title="ACC — AI Vehicle Insurance Platform")


@app.on_event("startup")
def _startup():
    db.init_db()

BASE = os.path.dirname(__file__)
app.mount("/static", StaticFiles(directory=os.path.join(BASE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE, "templates"))

MAX_IMAGE_MB = 8
MAX_VIDEO_MB = 30


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/rc-lookup")
async def rc_lookup(reg: str = ""):
    if not reg or len(reg.strip()) < 6:
        return JSONResponse({"success": False, "error": "Please enter a valid registration number."}, status_code=400)
    result = await lookup_vehicle(reg)
    if not result.get("success"):
        return JSONResponse(result, status_code=404)
    return result


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
    try:
        db.save_document_record(form_data, result, doc_type, extracted)
    except Exception as e:
        print(f"[DB] could not save document record: {e}")
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
    if "error" not in result:
        try:
            db.save_video_record(result)
        except Exception as e:
            print(f"[DB] could not save video record: {e}")
    status = 400 if "error" in result else 200
    return JSONResponse(result, status_code=status)


@app.post("/api/analyze-photos")
async def analyze_photos_endpoint(photos: list[UploadFile] = File(...)):
    if len(photos) > 10:
        return JSONResponse({"error": "Maximum 10 photos allowed."}, status_code=413)
    photo_bytes = []
    for p in photos:
        data = await p.read()
        if len(data) > MAX_IMAGE_MB * 1024 * 1024:
            return JSONResponse({"error": f"Photo '{p.filename}' exceeds {MAX_IMAGE_MB}MB."}, status_code=413)
        photo_bytes.append(data)
    result = analyze_photos(photo_bytes)
    if "error" not in result:
        try:
            db.save_photo_record(result)
        except Exception as e:
            print(f"[DB] could not save photo record: {e}")
    status = 400 if "error" in result else 200
    return JSONResponse(result, status_code=status)


@app.get("/api/records")
async def get_records():
    try:
        return db.list_records()
    except Exception as e:
        return JSONResponse({"error": f"Could not load records: {e}"}, status_code=500)
