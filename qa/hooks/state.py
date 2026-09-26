"""Per-session state shared by the QA hooks (gitignored, under .claude/qa_state/)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".claude" / "qa_state"
sys.path.insert(0, str(ROOT / "qa"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def read_hook_input() -> dict:
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except Exception:  # noqa: BLE001 - never crash a hook on bad input
        return {}


def _path(session_id: str) -> Path:
    safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_") or "unknown"
    return STATE_DIR / f"{safe}.json"


def load(session_id: str) -> dict:
    p = _path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    return {"start": time.time(), "touched": [], "stop_blocks": 0}


def save(session_id: str, state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _path(session_id).write_text(json.dumps(state, indent=1), encoding="utf-8")
