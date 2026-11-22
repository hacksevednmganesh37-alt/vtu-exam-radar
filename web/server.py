"""RADAR DESK - the student-facing web app.

A student fills in: subject, exam date, weak modules, hours per day.
Radar Desk saves the request and posts it into the BAND room, @mentioning Radar Data.
Radar Data -> Radar Builder (-> Radar Data if more data is needed) -> Radar Builder -> PLAN_READY @Radar Desk.
The page polls /api/plan/<id> and shows the agents' conversation live, then the personal plan.

Run:  uv run uvicorn web.server:app --host 0.0.0.0 --port 8000
"""
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from radar import analysis
from radar.band_helper import DATA_NAME, DESK_NAME

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).resolve().parent / "static"

ROOM_ID = os.environ.get("RADAR_ROOM_ID", "e103bc88-242e-4edc-bd19-103a1eb7ada8")
DATA_ID = os.environ.get("RADAR_DATA_ID", "")
# Radar Desk posts with its own key; until that secret exists it falls back to Radar Builder's key.
DESK_KEY = os.environ.get("RADAR_DESK_KEY") or os.environ.get("RADAR_BUILDER_KEY", "")
POSTER_NAME = DESK_NAME if os.environ.get("RADAR_DESK_KEY") else "Radar Builder"
BAND_BASES = [b for b in [os.environ.get("BAND_API_URL"), "https://api.band.ai/api/v1", "https://app.band.ai/api/v1"] if b]

app = FastAPI(title="VTU Exam Radar")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class PlanRequest(BaseModel):
    code: str = Field(min_length=3, max_length=16)
    exam_date: str
    weak_modules: list[int] = []
    hours: float = Field(default=4, ge=1, le=14)


def post_to_band(content: str) -> None:
    body = json.dumps({"message": {"content": content,
                                   "mentions": [{"id": DATA_ID, "name": DATA_NAME}]}}).encode()
    last_error = None
    for base in BAND_BASES:
        req = urllib.request.Request(
            f"{base}/agent/chats/{ROOM_ID}/messages", data=body, method="POST",
            headers={"X-API-Key": DESK_KEY, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if resp.status in (200, 201):
                    return
                last_error = f"HTTP {resp.status}"
        except urllib.error.HTTPError as err:
            last_error = f"HTTP {err.code}: {err.read()[:200]!r}"
        except urllib.error.URLError as err:
            last_error = str(err.reason)
    raise RuntimeError(f"Could not post to BAND ({last_error})")


@app.get("/")
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/subjects")
def subjects():
    names = {s["code"]: s["name"] for s in analysis.read_json(analysis.SITE_DATA / "subjects.json", [])}
    codes = sorted(p.name for p in analysis.PAPERS.iterdir() if p.is_dir())
    return [{"code": c, "name": names.get(c, c)} for c in codes]


@app.post("/api/plan")
def create_plan(p: PlanRequest):
    code = p.code.strip().upper()
    if not (analysis.PAPERS / code).is_dir():
        raise HTTPException(404, f"No papers uploaded for {code} yet.")
    weak = sorted({m for m in p.weak_modules if 1 <= m <= 5})
    req_id = uuid.uuid4().hex[:10]
    request = {"id": req_id, "code": code, "exam_date": p.exam_date, "weak_modules": weak,
               "hours": p.hours, "status": "working", "events": [], "created": analysis.now()}
    analysis.save_request(request)
    days = analysis.days_until(p.exam_date)
    analysis.log_message(code, DESK_NAME, DATA_NAME,
                         f"New student request: {code}, exam in {days} day(s), {p.hours:g}h/day"
                         + (f", weak in Module {', '.join(map(str, weak))}" if weak else "") + ".", req_id)
    try:
        post_to_band(f"@{DATA_NAME} analyse {code} days={days} req={req_id} requested_by=")
    except RuntimeError as err:
        request = analysis.load_request(req_id)
        request["status"] = "error"
        request["error"] = str(err)
        analysis.save_request(request)
        raise HTTPException(502, str(err))
    return {"id": req_id}


@app.get("/api/plan/{req_id}")
def get_plan(req_id: str):
    request = analysis.load_request(req_id)
    if not request:
        raise HTTPException(404, "Unknown request")
    return request


@app.get("/api/health")
def health():
    return {"ok": True, "poster": POSTER_NAME, "room": ROOM_ID, "data_agent_id_set": bool(DATA_ID)}
