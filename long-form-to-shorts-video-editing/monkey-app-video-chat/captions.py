"""Builds the burned-in caption style copied from the reference short: short
2-3 word phrases, bold all-caps text, white with a hot-pink karaoke-style
sweep across whichever word is currently being spoken, sitting in the black
letterbox band below the cropped speaker footage.

Takes faster-whisper's word-level timestamps and emits an .ass subtitle file
that ffmpeg burns in via the `ass` filter.
"""
from dataclasses import dataclass

PINK = "&H00782DFF"  # ASS BGR for hot pink RGB(255,45,120)
WHITE = "&H00FFFFFF"


@dataclass
class Word:
    text: str
    start: float
    end: float


def group_words_into_chunks(
    words: list[Word], max_words: int = 3, max_gap: float = 0.6
) -> list[list[Word]]:
    """Splits a word stream into short caption phrases, breaking on a max word
    count or a pause between words -- matches the ~2-3 word chunks seen in the
    reference (e.g. "I THINK YOU" / "BE IN TEXAS")."""
    chunks: list[list[Word]] = []
    current: list[Word] = []
    for word in words:
        if current and (len(current) >= max_words or word.start - current[-1].end > max_gap):
            chunks.append(current)
            current = []
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def _fmt_ts(seconds: float) -> str:
    cs = round(seconds * 100)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _phrase_line(words: list[Word], active_index: int, pos_y: int | None, video_w: int) -> str:
    prefix = f"{{\\pos({video_w // 2},{pos_y})}}" if pos_y is not None else ""
    parts = []
    for i, w in enumerate(words):
        text = w.text.upper()
        if i == active_index:
            parts.append(f"{{\\1c{PINK}&}}{text}{{\\1c{WHITE}&}}")
        else:
            parts.append(text)
    return prefix + " ".join(parts)


def build_ass(
    words: list[Word],
    video_w: int = 1080,
    video_h: int = 1920,
    margin_v: int = 300,
    max_words_per_chunk: int = 3,
    max_gap: float = 0.6,
    font: str = "Arial Black",
    font_size: int = 78,
    y_at=None,  # optional callable(t: float) -> int; overrides margin_v per-chunk based on layout at that time
) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{font_size},{WHITE},{WHITE},&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,3,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for chunk in group_words_into_chunks(words, max_words_per_chunk, max_gap):
        chunk_end = chunk[-1].end
        for i, w in enumerate(chunk):
            seg_start = w.start
            seg_end = chunk[i + 1].start if i + 1 < len(chunk) else chunk_end
            if seg_end <= seg_start:
                continue
            pos_y = y_at(seg_start) if y_at is not None else None
            text = _phrase_line(chunk, i, pos_y, video_w)
            lines.append(
                f"Dialogue: 0,{_fmt_ts(seg_start)},{_fmt_ts(seg_end)},Caption,,0,0,0,,{text}\n"
            )
    return "".join(lines)


def write_ass_file(words: list[Word], out_path: str, **kwargs) -> None:
    content = build_ass(words, **kwargs)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
