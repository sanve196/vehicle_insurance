"""Database layer: stores verification + inspection records.

Uses PostgreSQL when DATABASE_URL is set (Render), else falls back to a
local SQLite file for development. Uploaded files are NOT stored — only the
structured results and metadata, which keeps storage tiny and avoids needing
object storage on the free tier.
"""
import os
import json
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

# Render provides DATABASE_URL like "postgres://..."; SQLAlchemy needs "postgresql://"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./records.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class DocumentRecord(Base):
    __tablename__ = "document_records"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    document_type = Column(String(40))
    verdict = Column(String(40))
    confidence = Column(Integer)
    registration_number = Column(String(40))
    owner_name = Column(String(120))
    details = Column(Text)  # JSON: full field comparison + extracted fields


class VideoRecord(Base):
    __tablename__ = "video_records"
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    recommendation = Column(String(40))
    frames_analyzed = Column(Integer)
    usable_frames = Column(Integer)
    worst_damage_signal = Column(String(20))
    details = Column(Text)  # JSON: per-frame reports


def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)


def save_document_record(form_data: dict, result: dict, doc_type: dict, extracted: dict):
    db = SessionLocal()
    try:
        rec = DocumentRecord(
            document_type=doc_type.get("type"),
            verdict=result.get("verdict"),
            confidence=result.get("confidence"),
            registration_number=form_data.get("registration_number") or None,
            owner_name=form_data.get("owner_name") or None,
            details=json.dumps({"fields": result.get("fields"), "extracted": extracted}),
        )
        db.add(rec)
        db.commit()
        return rec.id
    finally:
        db.close()


def save_video_record(result: dict):
    db = SessionLocal()
    try:
        rec = VideoRecord(
            recommendation=result.get("recommendation"),
            frames_analyzed=result.get("frames_analyzed"),
            usable_frames=result.get("usable_frames"),
            worst_damage_signal=result.get("worst_damage_signal"),
            details=json.dumps(result.get("frame_reports", [])),
        )
        db.add(rec)
        db.commit()
        return rec.id
    finally:
        db.close()


def list_records(limit: int = 25):
    db = SessionLocal()
    try:
        docs = db.query(DocumentRecord).order_by(DocumentRecord.id.desc()).limit(limit).all()
        vids = db.query(VideoRecord).order_by(VideoRecord.id.desc()).limit(limit).all()
        return {
            "documents": [
                {
                    "id": d.id,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                    "document_type": d.document_type,
                    "verdict": d.verdict,
                    "confidence": d.confidence,
                    "registration_number": d.registration_number,
                    "owner_name": d.owner_name,
                }
                for d in docs
            ],
            "videos": [
                {
                    "id": v.id,
                    "created_at": v.created_at.isoformat() if v.created_at else None,
                    "recommendation": v.recommendation,
                    "frames_analyzed": v.frames_analyzed,
                    "usable_frames": v.usable_frames,
                    "worst_damage_signal": v.worst_damage_signal,
                }
                for v in vids
            ],
        }
    finally:
        db.close()
