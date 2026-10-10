"""Print word timings for source ranges: python words.py 237 260 1070 1100 ..."""
import json, sys
segs = json.load(open("work/transcript.json", encoding="utf-8"))
a = list(map(float, sys.argv[1:]))
for lo, hi in zip(a[::2], a[1::2]):
    out = []
    for s in segs:
        for w in s["words"]:
            if lo <= w["s"] < hi:
                sp = "M" if (w.get("f0") or 999) < 165 else "H"
                out.append(f"{w['w'].strip()}[{w['s']:.2f}-{w['e']:.2f}{sp}]")
    print(f"== {lo}-{hi}: " + " ".join(out))
