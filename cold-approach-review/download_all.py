"""One-off downloader for the two cold-approach audio sessions shared via
Google Drive links. Pulls each Wireless GO .wav into cold-approach-review/input/<session>/.
"""
import gdown
from pathlib import Path

BASE = Path(__file__).parent / "input"

FILES = {
    "session1": [
        ("1YVR8Dy819QyBu5IdhZMNKeNBTQlztroM", "00010_Wireless_GO.wav"),
        ("1hrjpvufLHnPFlCEYwsarOICYQbyjl4F0", "00011_Wireless_GO.wav"),
        ("1LvVD1EF_q_MIF5I4d5UbHo7uIzMMxwmL", "00012_Wireless_GO.wav"),
        ("1aqz2ImAOwOkBVA_RbgA-6iAH21R8FUgQ", "00013_Wireless_GO.wav"),
        ("1cLsqCfraN-RYbNxfRpbPlkuCnpfHfNkl", "00014_Wireless_GO.wav"),
        ("1Jqwv5ik2EKl74Znjd4R9gkWpikg7BWmW", "00015_Wireless_GO.wav"),
    ],
    "session2": [
        ("1ly_hT8FlMn8Ms3NoZeoxoovjhodh257B", "00034_Wireless_GO.wav"),
        ("1x7baFqhUSbAvVYjOokzoPFBEWPAmO9zu", "00035_Wireless_GO.wav"),
        ("1bqE5a7IxIZijMI72rs6ZJvg9Wc3xU6oU", "00036_Wireless_GO.wav"),
    ],
}

for session, files in FILES.items():
    for file_id, name in files:
        dest = BASE / session / name
        if dest.exists():
            print(f"Already have {dest}")
            continue
        print(f"Downloading {name} -> {dest}")
        gdown.download(id=file_id, output=str(dest), quiet=False)

print("Done.")
