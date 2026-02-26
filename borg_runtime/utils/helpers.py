from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sarge import Capture, run


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "session"


def run_command_capture(command: str) -> tuple[int, str, str]:
    stdout_capture = Capture()
    stderr_capture = Capture()
    process = run(command, stdout=stdout_capture, stderr=stderr_capture)
    exit_code = int(process.returncode) if process.returncode is not None else 1
    stdout_text = stdout_capture.text or ""
    stderr_text = stderr_capture.text or ""
    return exit_code, stdout_text, stderr_text


def resolve_path(base_dir: str, target_path: str) -> Path:
    path = Path(target_path)
    if path.is_absolute():
        return path
    return (Path(base_dir).resolve() / path).resolve()


def parse_json_lines(lines: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    non_json: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            non_json.append(line)
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
        else:
            non_json.append(line)
    return events, non_json


def write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")))
            handle.write("\n")
