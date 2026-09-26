"""Run the project quality checks.

Usage:
  python qa/run_checks.py path [path ...]          fast checks on specific files
  python qa/run_checks.py --level full path ...    fast + full checks
  python qa/run_checks.py --changed                every modified/untracked file per git
  python qa/run_checks.py --list                   show registered checks

Exit code 0 = all pass, 1 = problems found.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checks  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass


def git_changed_files() -> list[Path]:
    out = subprocess.run(["git", "status", "--porcelain", "-uall"], cwd=checks.ROOT,
                         capture_output=True, text=True, encoding="utf-8").stdout
    files = []
    for line in out.splitlines():
        if line[:2].strip() == "D":
            continue
        name = line[3:].split(" -> ")[-1].strip('"')
        files.append(checks.ROOT / name)
    return files


def format_report(results: dict[str, list[str]]) -> str:
    lines = []
    for path, problems in results.items():
        lines.append(f"{path}")
        lines += [f"  - {p}" for p in problems]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--level", choices=["fast", "full"], default="fast")
    ap.add_argument("--changed", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    checks.load_all()
    if args.list:
        for c in checks.REGISTRY:
            print(f"{c.level:4}  {c.name:28} exts={sorted(c.exts) if c.exts else 'any'} paths={c.path_glob or 'any'}")
        return 0

    paths = [Path(p).resolve() for p in args.paths]
    if args.changed:
        paths += git_changed_files()
    results = checks.run(paths, args.level)
    if results:
        print(format_report(results))
        return 1
    print(f"QA pass ({len(paths)} file(s), level={args.level})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
