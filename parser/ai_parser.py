import anthropic
import json
import re

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are an expert semiconductor tool log parser for Micron Technology.
Your job is to analyze tool log samples and extract structured data.

The log may be a SAMPLE from a very large file (beginning + middle + end sections).
Treat the sample as representative of the entire file.

Respond with ONLY valid JSON — no markdown, no explanation, no extra text.

Return EXACTLY this structure:
{
  "format_detected": "string (JSON/XML/CSV/TEXT/SYSLOG/KEY_VALUE/BINARY)",
  "tool_type": "string (e.g. Dry Etch Tool, EUV Scanner, CVD Chamber, CMP Tool, Ion Implant)",
  "records": [
    {
      "tool_id": "string",
      "timestamp": "string",
      "event_type": "string (SENSOR_DATA/ALARM/PROCESS_STEP/RECIPE/SYSTEM_EVENT/DIAGNOSTIC)",
      "severity": "string (INFO/WARNING/ERROR/CRITICAL)",
      "parameters": {"key": "value"},
      "alarms": ["alarm strings if any"],
      "summary": "string (max 25 words)",
      "raw_snippet": "string (max 60 chars from original)"
    }
  ],
  "overall_summary": "string (3-4 sentences describing the full log, mention total record count if known)"
}

STRICT RULES:
- Extract up to 8 records maximum from the sample
- Each summary must be under 25 words
- raw_snippet must be under 60 chars
- severity: INFO / WARNING / ERROR / CRITICAL only
- event_type: SENSOR_DATA / ALARM / PROCESS_STEP / RECIPE / SYSTEM_EVENT / DIAGNOSTIC only
- ALL JSON brackets must be properly closed
- Never leave JSON incomplete
- If the file is large, mention the scale in overall_summary
"""


def fix_json(raw: str) -> dict:
    """Try multiple strategies to parse potentially malformed JSON."""
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"```$", "", raw).strip()

    
    try:
        return json.loads(raw)
    except Exception:
        pass

    
    try:
        opens_c = raw.count('{')
        closes_c = raw.count('}')
        opens_b = raw.count('[')
        closes_b = raw.count(']')
        fixed = raw.rstrip().rstrip(',')
        fixed += ']' * max(0, opens_b - closes_b)
        fixed += '}' * max(0, opens_c - closes_c)
        return json.loads(fixed)
    except Exception:
        pass

    
    try:
        last_brace = raw.rfind('}')
        if last_brace > 0:
            trimmed = raw[:last_brace + 1].rstrip().rstrip(',')
            trimmed += ']}'
            return json.loads(trimmed)
    except Exception:
        pass

    
    try:
        records = []
        summaries = re.findall(r'"summary"\s*:\s*"([^"]+)"', raw)
        tool_ids = re.findall(r'"tool_id"\s*:\s*"([^"]+)"', raw)
        timestamps = re.findall(r'"timestamp"\s*:\s*"([^"]+)"', raw)
        severities = re.findall(r'"severity"\s*:\s*"([^"]+)"', raw)
        event_types = re.findall(r'"event_type"\s*:\s*"([^"]+)"', raw)

        for i, s in enumerate(summaries[:8]):
            records.append({
                "tool_id": tool_ids[i] if i < len(tool_ids) else "UNKNOWN",
                "timestamp": timestamps[i] if i < len(timestamps) else "",
                "event_type": event_types[i] if i < len(event_types) else "SYSTEM_EVENT",
                "severity": severities[i] if i < len(severities) else "INFO",
                "parameters": {},
                "alarms": [],
                "summary": s,
                "raw_snippet": ""
            })

        fmt = re.search(r'"format_detected"\s*:\s*"([^"]+)"', raw)
        tool = re.search(r'"tool_type"\s*:\s*"([^"]+)"', raw)

        if records:
            return {
                "format_detected": fmt.group(1) if fmt else "UNKNOWN",
                "tool_type": tool.group(1) if tool else "Semiconductor Tool",
                "records": records,
                "overall_summary": f"Extracted {len(records)} records from log sample using fallback parsing."
            }
    except Exception:
        pass

    return None


def parse_with_ai(log_text: str, fmt: str, filename: str, metadata: dict = None) -> dict:
    """Send log sample to Claude for intelligent parsing."""

    meta_note = ""
    if metadata:
        if metadata.get("truncated"):
            meta_note = f"\n\nFILE INFO: This is a SAMPLED portion of a large file. {metadata.get('note', '')}. Analyze this sample as representative of the entire file and mention the full scale in your overall_summary."
        elif metadata.get("note"):
            meta_note = f"\n\nFILE INFO: {metadata.get('note')}"

    user_message = f"""Parse this semiconductor tool log.
Filename: {filename}
Detected Format: {fmt}{meta_note}

LOG CONTENT:
{log_text}"""

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text
        result = fix_json(raw)

        if result:
            
            if metadata and metadata.get("total_records", 0) > 0:
                total = metadata["total_records"]
                existing = result.get("overall_summary", "")
                if str(total) not in existing:
                    result["overall_summary"] = (
                        f"[Large file: {total} total records detected] " + existing
                    )
            return result

        raise ValueError("All JSON parsing strategies failed")

    except Exception as e:
        return {
            "format_detected": fmt,
            "tool_type": "Unknown",
            "records": [{
                "tool_id": "UNKNOWN",
                "timestamp": "",
                "event_type": "SYSTEM_EVENT",
                "severity": "ERROR",
                "parameters": {},
                "alarms": [str(e)[:120]],
                "summary": f"Parsing error: {str(e)[:80]}",
                "raw_snippet": log_text[:60]
            }],
            "overall_summary": f"Parsing failed: {str(e)[:120]}"
        }
