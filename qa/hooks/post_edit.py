"""PostToolUse hook (Write/Edit/MultiEdit/NotebookEdit): run fast checks on the file just written.

Problems go to stderr with exit code 2, which Claude Code feeds straight back to the
agent so it fixes them immediately instead of the user finding them later.
"""
import sys
from pathlib import Path

import state
import checks

data = state.read_hook_input()
tool_input = data.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
if not file_path:
    sys.exit(0)

path = Path(file_path).resolve()
sid = data.get("session_id", "unknown")
st = state.load(sid)
rel = checks.rel_path(path)
if rel not in st["touched"]:
    st["touched"].append(rel)
state.save(sid, st)

checks.load_all()
results = checks.run([path], "fast")
if results:
    lines = [f"QA fast checks failed for {rel}. Fix these now before moving on:"]
    lines += [f"  - {p}" for p in results.get(rel, [])]
    print("\n".join(lines), file=sys.stderr)
    sys.exit(2)
