import uuid
import sys
import hashlib
import secrets
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

from parser.detector import detect_format, preprocess
from parser.ai_parser import parse_with_ai
from database.db import init_db, save_parsed_records, get_all_sessions, get_session_records, get_stats

# ── Auth ─────────────────────────────────────────────────
USERNAME = "Team Algorithm"
PASSWORD = "AlgorithmChampions2026"
PASSWORD_HASH = hashlib.sha256(PASSWORD.encode()).hexdigest()
SESSIONS = set()

def is_auth(request: Request) -> bool:
    return request.cookies.get("session_token") in SESSIONS

app = FastAPI(title="Micron Smart Tool Log Parser", version="2.0.0")

init_db()

# Auto-generate sample logs on startup
def startup_setup():
    logs_dir = Path(__file__).parent / "synthetic" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    if not any(logs_dir.iterdir()):
        try:
            from synthetic.generator import generate_all
            generate_all()
        except Exception as e:
            print(f"Could not generate sample logs: {e}")

startup_setup()

# Mount static files
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/")
async def root():
    # Always serve index.html — login is handled inside it
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))


@app.post("/api/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")
    if username == USERNAME and hashlib.sha256(password.encode()).hexdigest() == PASSWORD_HASH:
        token = secrets.token_hex(32)
        SESSIONS.add(token)
        response = JSONResponse({"success": True})
        response.set_cookie("session_token", token, httponly=True, max_age=86400 * 7, samesite="lax")
        return response
    return JSONResponse({"success": False, "message": "Invalid username or password"}, status_code=401)


@app.post("/api/logout")
async def logout(request: Request):
    token = request.cookies.get("session_token")
    SESSIONS.discard(token)
    response = JSONResponse({"success": True})
    response.delete_cookie("session_token")
    return response


@app.get("/api/check-auth")
async def check_auth(request: Request):
    return JSONResponse({"authenticated": is_auth(request)})


@app.post("/api/parse")
async def parse_log(request: Request, file: UploadFile = File(...)):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        content = await file.read()
        filename = file.filename or "unknown.log"
        fmt = detect_format(filename, content)
        log_text, metadata = preprocess(content, fmt)
        result = parse_with_ai(log_text, fmt, filename, metadata)
        session_id = str(uuid.uuid4())[:8].upper()
        records = result.get("records", [])
        save_parsed_records(session_id, filename, fmt, records)
        return JSONResponse({
            "session_id": session_id,
            "filename": filename,
            "format": fmt,
            "tool_type": result.get("tool_type", "Unknown"),
            "overall_summary": result.get("overall_summary", ""),
            "record_count": len(records),
            "total_records_in_file": metadata.get("total_records", 0),
            "file_size_kb": round(metadata.get("size_kb", 0), 1),
            "was_sampled": metadata.get("truncated", False),
            "records": records
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_all_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    records = get_session_records(session_id)
    if not records:
        raise HTTPException(status_code=404, detail="Session not found")
    return records


@app.delete("/api/sessions/all")
async def delete_all_sessions(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    from database.db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM parsed_logs")
    conn.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    return {"message": "All sessions deleted"}


@app.get("/api/stats")
async def stats(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return get_stats()


@app.get("/api/sample-logs")
async def list_sample_logs(request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    logs_dir = Path(__file__).parent / "synthetic" / "logs"
    if not logs_dir.exists():
        return []
    return [{"name": f.name, "size": f.stat().st_size} for f in logs_dir.iterdir() if f.is_file()]


@app.get("/api/sample-logs/{filename}")
async def get_sample_log(filename: str, request: Request):
    if not is_auth(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    logs_dir = Path(__file__).parent / "synthetic" / "logs"
    path = logs_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample not found")
    content = path.read_bytes()
    fmt = detect_format(filename, content)
    log_text, metadata = preprocess(content, fmt)
    result = parse_with_ai(log_text, fmt, filename, metadata)
    session_id = str(uuid.uuid4())[:8].upper()
    records = result.get("records", [])
    save_parsed_records(session_id, filename, fmt, records)
    return JSONResponse({
        "session_id": session_id,
        "filename": filename,
        "format": fmt,
        "tool_type": result.get("tool_type", "Unknown"),
        "overall_summary": result.get("overall_summary", ""),
        "record_count": len(records),
        "total_records_in_file": metadata.get("total_records", 0),
        "file_size_kb": round(metadata.get("size_kb", 0), 1),
        "was_sampled": metadata.get("truncated", False),
        "records": records
    })


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
