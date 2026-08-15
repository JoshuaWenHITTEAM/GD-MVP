import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import yaml

STRUCTURED_LOG_RE = re.compile(r"\[(TRAIN_[A-Z]+)\]\s+(\{.*\})")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a mapping")
    return data


def save_yaml(path: Path, data: Dict[str, Any]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)


def parse_structured_log_line(line: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    match = STRUCTURED_LOG_RE.search(line)
    if not match:
        return None, None
    event_name, payload = match.groups()
    try:
        return event_name, json.loads(payload)
    except json.JSONDecodeError:
        return None, None


def sse_message(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
