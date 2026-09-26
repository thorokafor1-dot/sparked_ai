"""Stop hook: the Definition of Done gate.

Before the agent ends its turn, run fast + full checks on every file THIS session
produced: Write/Edit targets (post_edit.py) plus renders and changed files that appeared
while one of this session's Bash/PowerShell commands was running (command_window.py).
Work by other sessions running in parallel is never attributed here.
If anything fails, block the stop and hand the agent the problem list to fix.

Loop guard: after MAX_BLOCKS consecutive blocks the agent is allowed to stop, and the
remaining problems are shown to the user instead of looping forever.
"""
import json
import re
import sys

import state
import checks

MAX_BLOCKS = 3

data = state.read_hook_input()
sid = data.get("session_id", "unknown")
st = state.load(sid)

paths = {checks.ROOT / rel for rel in st["touched"] + st.get("produced", [])}

# Only the newest version of each output (short_1_v32 supersedes v31).
latest = {}
for p in paths:
    key = (p.parent, re.sub(r"_v\d+$", "", p.stem), p.suffix.lower())
    try:
        if key not in latest or p.stat().st_mtime > latest[key].stat().st_mtime:
            latest[key] = p
    except OSError:
        pass
paths = set(latest.values())

checks.load_all()
results = checks.run(sorted(paths), "full")

if not results:
    st["stop_blocks"] = 0
    state.save(sid, st)
    sys.exit(0)

report = run_checks.format_report(results)
if st["stop_blocks"] >= MAX_BLOCKS:
    st["stop_blocks"] = 0
    state.save(sid, st)
    print(json.dumps({"systemMessage": f"QA gate: still failing after {MAX_BLOCKS} fix attempts, "
                                       f"needs a human look:\n{report}"}))
    sys.exit(0)

st["stop_blocks"] += 1
state.save(sid, st)
print(json.dumps({
    "decision": "block",
    "reason": (f"QA gate (attempt {st['stop_blocks']}/{MAX_BLOCKS}): these files fail checks. "
               f"Fix them, then finish. If a finding is a false positive, fix the check in qa/ "
               f"instead of ignoring it.\n{report}"),
}))
