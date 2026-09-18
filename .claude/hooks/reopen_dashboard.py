import json
import subprocess
import sys

DASHBOARD_URL = "https://claude.ai/artifact/BEaQ5nvtAUr9cuWgKm5Xyd"
TRIGGER_DIR = "outlier-tracking"

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

tool_input = data.get("tool_input") or {}
tool_response = data.get("tool_response") or {}
file_path = tool_input.get("file_path") or tool_response.get("filePath") or ""
file_path = file_path.replace("\\", "/")

if TRIGGER_DIR in file_path:
    subprocess.run(["cmd", "/c", "start", "", DASHBOARD_URL])
