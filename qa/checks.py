"""Shared quality checks for the whole Sparked AI project.

Every check is a function registered with @check. It receives a Path and returns a
list of problem strings (empty list = pass). Each problem should say exactly what is
wrong and where, so the agent can fix it without asking the user.

Levels:
  fast  runs after every Write/Edit (must finish in well under a second per file)
  full  runs before the agent ends its turn (can be slower: ffprobe, image analysis)

Folder-specific checks live in qa/checks_<area>.py and are auto-loaded by load_all().
When the user catches a mistake a check missed, add a check here (or in the matching
checks_<area>.py) so it can never slip through again.
"""
from __future__ import annotations

import ast
import importlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
EM_DASH = "\u2014"

TEXT_EXTS = {".md", ".txt", ".html", ".htm", ".py", ".js", ".ts", ".css", ".yml",
             ".yaml", ".ass", ".srt", ".vtt", ".csv", ".toml", ".ini", ".cfg"}

# Generated outputs that live in gitignored folders, so git status never reports them.
# The stop gate checks any of these created or changed during the session.
OUTPUT_GLOBS = [
    "long-form-to-shorts-video-editing/*/output/*.mp4",
    "long-form-to-shorts-video-editing/*/work/*.ass",
    "long-form-video-editing/*/output/*.mp4",
    "long-form-video-editing/*/out/*.mp4",
    "thumbnail-creation/output/*.png",
    "thumbnail-creation/output/*.jpg",
]
CACHE_FILE = ROOT / ".claude" / "qa_state" / "cache.json"

# Folders holding external/source material or generated media we didn't author.
SKIP_DIR_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv", "gfpgan",
                  "models", "input", "raw", "reference", "grok-swipe-pack", "audio"}


@dataclass
class Check:
    name: str
    fn: Callable[[Path], list[str]]
    level: str = "fast"
    exts: set[str] | None = None          # None = any extension
    path_glob: list[str] = field(default_factory=list)  # repo-relative globs; empty = anywhere
    exclude_glob: list[str] = field(default_factory=list)
    cache: bool = False  # slow checks (ffmpeg, image analysis): reuse result while the file is unchanged

    def applies(self, path: Path) -> bool:
        if self.exts is not None and path.suffix.lower() not in self.exts:
            return False
        rel = rel_path(path)
        if self.path_glob and not any(Path(rel).match(g) or _glob_match(rel, g) for g in self.path_glob):
            return False
        if any(Path(rel).match(g) or _glob_match(rel, g) for g in self.exclude_glob):
            return False
        return True


REGISTRY: list[Check] = []


def check(name: str, level: str = "fast", exts=None, paths=None, exclude=None, cache=False):
    def deco(fn):
        REGISTRY.append(Check(name, fn, level, set(exts) if exts else None,
                              list(paths or []), list(exclude or []), cache))
        return fn
    return deco


def rel_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _glob_match(rel: str, pattern: str) -> bool:
    """fnmatch-style match where ** spans folders."""
    regex = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(regex, rel) is not None


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_PARTS for part in Path(rel_path(path)).parts[:-1])


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


# ---------------------------------------------------------------- generic checks

# *_dump.txt files are raw scraped YouTube titles/thumbnail text: external data, not our copy.
@check("no-em-dash", exts=TEXT_EXTS, exclude=["**/*_dump.txt"])
def no_em_dash(path: Path) -> list[str]:
    """CLAUDE.md formatting rule: never use an em dash anywhere."""
    text = read_text(path)
    if text is None:
        return []
    hits = [i for i, line in enumerate(text.splitlines(), 1) if EM_DASH in line]
    if not hits:
        return []
    shown = ", ".join(map(str, hits[:15])) + (" ..." if len(hits) > 15 else "")
    return [f"em dash on line(s) {shown}; replace with a comma, period, parentheses, or rewrite"]


# .json is excluded from TEXT_EXTS above because outlier-tracking/*/data.json legitimately
# quotes real YouTube titles verbatim (those often contain em dashes and aren't our copy).
# The strategist's own JSON is different: ideas_source.py strips em dashes from evidence
# titles at build time, so any em dash here is a real regression, not quoted external data.
@check("no-em-dash-strategist-json", paths=["video-ideation/strategist/ideas.json", "video-ideation/strategist/formats.json"], exts={".json"})
def no_em_dash_strategist_json(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return []
    hits = [i for i, line in enumerate(text.splitlines(), 1) if EM_DASH in line]
    if not hits:
        return []
    return [f"em dash on line(s) {', '.join(map(str, hits[:15]))}; fix the em-dash strip in ideas_source.py's find(), don't hand-edit the .json"]


@check("no-merge-markers", exts=TEXT_EXTS | {".json"})
def no_merge_markers(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return []
    hits = [i for i, line in enumerate(text.splitlines(), 1)
            if line.startswith(("<<<<<<< ", ">>>>>>> ")) or line == "======="]
    return [f"git merge conflict marker on line {i}" for i in hits[:5]]


@check("valid-json", exts={".json"})
def valid_json(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return ["JSON file is not valid UTF-8"]
    try:
        json.loads(text)
    except json.JSONDecodeError as e:
        return [f"invalid JSON: {e.msg} at line {e.lineno} col {e.colno}"]
    return []


@check("valid-python", exts={".py"})
def valid_python(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return ["Python file is not valid UTF-8"]
    try:
        ast.parse(text.lstrip("\ufeff"), filename=str(path))  # Python itself accepts a BOM
    except SyntaxError as e:
        return [f"Python syntax error line {e.lineno}: {e.msg}"]
    return []


@check("valid-yaml", exts={".yml", ".yaml"})
def valid_yaml(path: Path) -> list[str]:
    try:
        import yaml
    except ImportError:
        return []
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - any parse failure is the finding
        return [f"invalid YAML: {e}".splitlines()[0]]
    return []


SECRET_PATTERNS = {
    "Google API key": re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    "Anthropic API key": re.compile(r"sk-ant-[0-9A-Za-z_\-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-(?:proj-)?[0-9A-Za-z]{32,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----"),
}


@check("no-hardcoded-secrets", exts=TEXT_EXTS | {".json"}, exclude=["**/.env", "**/token*.json", "**/client_secret*.json"])
def no_hardcoded_secrets(path: Path) -> list[str]:
    text = read_text(path)
    if text is None:
        return []
    return [f"looks like a hardcoded {label}; move it to an env var / .env (gitignored)"
            for label, rx in SECRET_PATTERNS.items() if rx.search(text)]


@check("python-imports-resolve", level="full", exts={".py"}, exclude=["qa/**"])
def python_imports_resolve(path: Path) -> list[str]:
    """Catch typos in top-level imports of third-party/stdlib modules before a real run does."""
    import importlib.util
    text = read_text(path)
    if text is None:
        return []
    try:
        tree = ast.parse(text.lstrip("\ufeff"))
    except SyntaxError:
        return []  # valid-python already reports it
    # Scripts here often sys.path.insert a parent folder to share helpers (common.py,
    # _common.py), so anything importable from the file's folder or an ancestor counts.
    local = set()
    for d in [path.parent, *path.parent.parents]:
        local |= {p.stem for p in d.glob("*.py")} | {p.name for p in d.iterdir() if p.is_dir()}
        if d == ROOT:
            break
    # Also handles the sibling-folder idiom used for shared utilities like tools/
    # denoise.py: sys.path.insert(0, str(Path(__file__).resolve().parents[N] / "name")),
    # which makes that folder's .py files importable as top-level modules even though
    # the folder isn't itself an ancestor of this file.
    for n_str, folder in re.findall(r"parents\[(\d+)\]\s*/\s*[\"'](\w[\w\-]*)[\"']", text):
        try:
            target = path.parents[int(n_str)] / folder
        except IndexError:
            continue
        if target.is_dir():
            local |= {p.stem for p in target.glob("*.py")}
    missing = []
    for node in tree.body:  # top-level only; guarded/optional imports inside try are skipped
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        for n in names:
            if n in local or n == "__future__":
                continue
            if importlib.util.find_spec(n) is None:
                missing.append(n)
    return [f"import '{n}' does not resolve (typo, or missing from requirements.txt / not installed)"
            for n in sorted(set(missing))]


# ---------------------------------------------------------------- loading + running

def load_all() -> None:
    """Import every qa/checks_<area>.py so their @check registrations take effect."""
    for mod in sorted(Path(__file__).parent.glob("checks_*.py")):
        try:
            importlib.import_module(mod.stem)  # qa/ is on sys.path; area modules do `from checks import check`
        except Exception as e:  # noqa: BLE001 - one broken module must not disable every other check
            LOAD_ERRORS.append(f"qa/{mod.name} failed to load ({type(e).__name__}: {e}); its checks are NOT running")


LOAD_ERRORS: list[str] = []


def _src_hash(fn: Callable) -> str:
    import hashlib
    import inspect
    # whole module + the shared media helpers, so constants (thresholds) and analyze() changes count too
    try:
        src = Path(inspect.getsourcefile(fn)).read_bytes() + (Path(__file__).parent / "media.py").read_bytes()
        # helper scripts the checks import from their tool folders (verify_*.py, reframe.py): a threshold
        # fix there must not be masked by a stale cached verdict
        for helper in sorted(ROOT.glob("*/*/verify_*.py")) + sorted(ROOT.glob("*/*/reframe.py")):
            src += helper.read_bytes()
        return hashlib.md5(src).hexdigest()[:8]
    except (OSError, TypeError):
        return "nosrc"


def run(paths: list[Path], level: str = "fast") -> dict[str, list[str]]:
    """Return {repo-relative path: [problem, ...]} for every path with problems."""
    levels = {"fast"} if level == "fast" else {"fast", "full"}
    results: dict[str, list[str]] = {}
    try:
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    cache_dirty = False
    for path in paths:
        if not path.is_file() or should_skip(path):
            continue
        problems = []
        for c in REGISTRY:
            if c.level in levels and c.applies(path):
                key = None
                if c.cache:
                    st = path.stat()
                    # the check's own source is part of the key, so editing a check re-runs it
                    key = f"{c.name}|{_src_hash(c.fn)}|{rel_path(path)}|{st.st_mtime_ns}|{st.st_size}"
                    if key in cache:
                        problems += [f"[{c.name}] {p}" for p in cache[key]]
                        continue
                try:
                    found = c.fn(path)
                    # never cache a verdict on a file that was still settling: checks skip in-progress
                    # renders, and caching that skip once let a broken render (v8, 18s of audio lost) pass
                    if key and __import__("time").time() - st.st_mtime > 30:
                        cache[key] = found
                        cache_dirty = True
                    problems += [f"[{c.name}] {p}" for p in found]
                except Exception as e:  # noqa: BLE001 - a crashing check must not hide others
                    problems.append(f"[{c.name}] check crashed: {type(e).__name__}: {e}")
        if problems:
            results[rel_path(path)] = problems
    if cache_dirty:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
    if LOAD_ERRORS:
        results["qa (checker modules)"] = LOAD_ERRORS
    return results


def recent_outputs(since: float) -> list[Path]:
    """Generated media outputs (OUTPUT_GLOBS) modified at or after `since` (epoch seconds).

    Only the newest version of each output is returned (short_1_v31 supersedes v29/v30),
    so iterating on a render doesn't re-analyze every discarded draft.
    """
    latest: dict[tuple, Path] = {}
    for g in OUTPUT_GLOBS:
        for p in ROOT.glob(g):
            try:
                mtime = p.stat().st_mtime
            except OSError:
                continue
            if mtime < since:
                continue
            key = (p.parent, re.sub(r"_v\d+$", "", p.stem), p.suffix.lower())
            if key not in latest or mtime > latest[key].stat().st_mtime:
                latest[key] = p
    return list(latest.values())
