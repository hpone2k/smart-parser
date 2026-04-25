import json
import xml.etree.ElementTree as ET
import csv
import io
import re


def detect_format(filename: str, content: bytes) -> str:
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    if ext == "json": return "JSON"
    if ext == "xml":  return "XML"
    if ext == "csv":  return "CSV"
    if ext in ("bin","dat"): return "BINARY"

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:
        return "BINARY"

    try:
        json.loads(text)
        return "JSON"
    except Exception:
        pass

    try:
        ET.fromstring(text)
        return "XML"
    except Exception:
        pass

    try:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) > 1 and len(rows[0]) > 2:
            return "CSV"
    except Exception:
        pass

    if re.search(r"^[0-9A-Fa-f\s]+$", text.strip()) and len(text) > 20:
        return "HEX"
    if re.search(r"\w+\s+\d+\s+\d+:\d+:\d+\s+\S+\s+\w+", text):
        return "SYSLOG"
    if re.search(r"\w+=[\w\d\.\-]+", text) and not re.search(r"<|>|\{|\}", text):
        return "KEY_VALUE"
    return "TEXT"


def smart_sample_lines(lines: list, max_lines: int = 40) -> tuple:
    """Sample from beginning, middle, and end of a list of lines."""
    total = len(lines)
    if total <= max_lines:
        return lines, total, False

    chunk = max_lines // 3
    mid = total // 2

    sampled = (
        lines[:chunk]
        + [f"... [{total - max_lines} lines omitted — file has {total} total lines] ..."]
        + lines[mid:mid + chunk]
        + ["... [skipping to end] ..."]
        + lines[-chunk:]
    )
    return sampled, total, True


def smart_sample_csv(text: str, max_rows: int = 40) -> tuple:
    """Smart CSV sampling: header + rows from beginning, middle, end."""
    lines = text.splitlines()
    if not lines:
        return text, 0, False

    header = lines[0]
    data = lines[1:]
    total = len(data)

    if total <= max_rows:
        return text, total, False

    chunk = max_rows // 3
    mid = total // 2

    sampled = (
        [header]
        + data[:chunk]
        + [f"... [{total - max_rows} rows omitted — {total} total data rows] ..."]
        + data[mid:mid + chunk]
        + ["... [skipping to end] ..."]
        + data[-chunk:]
    )
    return "\n".join(sampled), total, True


def smart_sample_json(content: bytes, max_chars: int = 5000) -> tuple:
    """Smart JSON sampling: extract structure + sample records from large arrays."""
    try:
        text = content.decode("utf-8", errors="replace")

        if len(text) <= max_chars:
            return text, 0, False

        data = json.loads(text)

        def find_large_arrays(obj, path="root", depth=0):
            results = []
            if depth > 6: return results
            if isinstance(obj, list) and len(obj) > 5:
                results.append((path, obj))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    results.extend(find_large_arrays(v, f"{path}.{k}", depth + 1))
            return results

        arrays = find_large_arrays(data)

        if arrays:
            path, arr = max(arrays, key=lambda x: len(x[1]))
            total = len(arr)
            chunk = 5
            mid = total // 2

            sample_records = arr[:chunk] + arr[mid:mid + chunk] + arr[-chunk:]

            summary = {"_file_info": {
                "total_records_in_array": total,
                "array_path": path,
                "sampled_records": len(sample_records),
                "sampling_strategy": "beginning + middle + end",
                "note": f"Large file sampled. Representing {total} total records."
            }}

            if isinstance(data, dict):
                for k, v in data.items():
                    if not isinstance(v, list) and len(str(v)) < 300:
                        summary[k] = v

            summary["sampled_records"] = sample_records

            sampled_text = json.dumps(summary, indent=2)
            return sampled_text, total, True

        
        lines = text.splitlines()
        sampled, total_lines, _ = smart_sample_lines(lines, max_lines=60)
        return "\n".join(sampled), total_lines, True

    except Exception:
        text = content.decode("utf-8", errors="replace")
        lines = text.splitlines()
        sampled, total, truncated = smart_sample_lines(lines, 60)
        return "\n".join(sampled), total, truncated


def preprocess(content: bytes, fmt: str) -> tuple:
    """
    Process raw file content into AI-ready text + metadata.
    Returns (text, metadata_dict)
    """
    size_kb = len(content) / 1024
    size_mb = size_kb / 1024

    if fmt == "BINARY":
        hex_str = content.hex()
        chunks = [hex_str[i:i+32] for i in range(0, min(len(hex_str), 512), 32)]
        return "BINARY/HEX LOG:\n" + "\n".join(chunks), {"size_kb": size_kb, "total_records": 0, "truncated": False}

    if fmt == "HEX":
        text = content.decode("utf-8", errors="replace")
        return f"HEX ENCODED LOG:\n{text[:3000]}", {"size_kb": size_kb, "total_records": 0, "truncated": False}

    if fmt == "CSV":
        text = content.decode("utf-8", errors="replace")
        sampled, total, truncated = smart_sample_csv(text, max_rows=40)
        return sampled, {
            "size_kb": size_kb,
            "total_records": total,
            "truncated": truncated,
            "note": f"{total} data rows · {size_mb:.2f} MB · sampled beginning/middle/end" if truncated else f"{total} rows"
        }

    if fmt == "JSON":
        sampled, total, truncated = smart_sample_json(content, max_chars=5000)
        return sampled, {
            "size_kb": size_kb,
            "total_records": total,
            "truncated": truncated,
            "note": f"{total} records detected · {size_mb:.2f} MB · sampled beginning/middle/end" if truncated else ""
        }

    
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()
    sampled_lines, total, truncated = smart_sample_lines(lines, max_lines=60)
    sampled = "\n".join(sampled_lines)
    return sampled, {
        "size_kb": size_kb,
        "total_records": total,
        "truncated": truncated,
        "note": f"{total} lines · {size_mb:.2f} MB · sampled beginning/middle/end" if truncated else f"{total} lines"
    }
