"""SessionStart hook: record when the session began so the stop gate knows which files are new."""
import time

import state

data = state.read_hook_input()
sid = data.get("session_id", "unknown")
st = state.load(sid)
if data.get("source") in (None, "startup", "clear"):
    st["start"] = time.time()
state.save(sid, st)
