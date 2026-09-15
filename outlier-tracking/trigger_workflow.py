import os
import subprocess
import json

# Get GitHub token
token = os.getenv('GITHUB_TOKEN')
if not token:
    print("ERROR: GITHUB_TOKEN environment variable not set")
    exit(1)

# Prepare the request
url = "https://api.github.com/repos/thorokafor1-dot/sparked_ai/actions/workflows/youtube_outlier_tracker.yml/dispatches"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json"
}
data = {"ref": "main"}

# Use curl to make the request
cmd = [
    "curl",
    "-X", "POST",
    "-H", f"Authorization: Bearer {token}",
    "-H", "Accept: application/vnd.github.v3+json",
    "-d", json.dumps(data),
    url
]

try:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✓ Workflow triggered successfully")
        print(f"Response: {result.stdout}")
    else:
        print(f"ERROR: {result.stderr}")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
