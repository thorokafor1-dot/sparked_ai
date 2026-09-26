"""PreToolUse/PostToolUse hook for Bash and PowerShell: attribute outputs to this session.

Pre records when the command started. Post records every render/thumbnail (OUTPUT_GLOBS)
and git-changed file modified during that window as this session's work. That way the stop
gate checks what this session produced and never blocks on another session's work
running in parallel.

Limitation: a run_in_background command returns immediately, so its outputs land after
the window closes. Check those by hand with qa/run_checks.py (root CLAUDE.md rule).
"""
import sys
import time

import state
import checks
import run_checks

data = state.read_hook_input()
sid = data.get("session_id", "unknown")
st = state.load(sid)

if data.get("hook_event_name") == "PreToolUse":
    st["cmd_start"] = time.time()
    state.save(sid, st)
    sys.exit(0)

since = st.pop("cmd_start", None)
if since is None:
    sys.exit(0)
since -= 1  # filesystem mtime granularity
found = checks.recent_outputs(since)
for p in run_checks.git_changed_files():
    try:
        if p.is_file() and p.stat().st_mtime >= since:
            found.append(p)
    except OSError:
        pass
produced = st.setdefault("produced", [])
for p in found:
    rel = checks.rel_path(p)
    if rel not in produced:
        produced.append(rel)
state.save(sid, st)
