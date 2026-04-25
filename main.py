import uuid
import sys
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).parent))

from parser.detector import detect_format, preprocess
from parser.ai_parser import parse_with_ai
from database.db import init_db, save_parsed_records, get_all_sessions, get_session_records, get_stats

app = FastAPI(title="Micron Smart Tool Log Parser", version="2.0.0")

init_db()

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


@app.get("/")
async def root():
    return FileResponse(str(Path(__file__).parent / "static" / "index.html"))


@app.post("/api/parse")
async def parse_log(file: UploadFile = File(...)):
    try:
        content = await file.read()
        filename = file.filename or "unknown.log"

        # Detect format
        fmt = detect_format(filename, content)

        # Smart preprocess — returns (text, metadata)
        log_text, metadata = preprocess(content, fmt)

        # AI parse with metadata context
        result = parse_with_ai(log_text, fmt, filename, metadata)

        # Save to DB
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions")
async def list_sessions():
    return get_all_sessions()


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    records = get_session_records(session_id)
    if not records:
        raise HTTPException(status_code=404, detail="Session not found")
    return records


@app.get("/api/stats")
async def stats():
    return get_stats()


@app.delete("/api/sessions/all")
async def delete_all_sessions():
    from database.db import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM parsed_logs")
    conn.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    return {"message": "All sessions deleted"}


@app.get("/api/sample-logs")
async def list_sample_logs():
    logs_dir = Path(__file__).parent / "synthetic" / "logs"
    if not logs_dir.exists():
        return []
    files = []
    for f in logs_dir.iterdir():
        if f.is_file():
            files.append({"name": f.name, "size": f.stat().st_size})
    return files


@app.get("/api/sample-logs/{filename}")
async def get_sample_log(filename: str):
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
