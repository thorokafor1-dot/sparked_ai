"""Flattens work/<session>/<stem>.json segment lists into plain, timestamped
text files at work/<session>/<stem>.txt for faster human/LLM reading.
"""
import json
from pathlib import Path

WORK_DIR = Path(__file__).parent / "work"


def fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def main() -> None:
    for json_path in sorted(WORK_DIR.glob("*/*.json")):
        txt_path = json_path.with_suffix(".txt")
        segments = json.loads(json_path.read_text(encoding="utf-8"))
        lines = [f"[{fmt_ts(seg['start'])}] {seg['text']}" for seg in segments]
        txt_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"Wrote {txt_path}")


if __name__ == "__main__":
    main()
