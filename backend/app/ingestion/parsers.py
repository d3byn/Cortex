import re
from pathlib import Path
from pypdf import PdfReader

# glyph-spaced pdfs fix

_SINGLE_CHAR_RATIO = 0.6
_MIN_TOKENS = 20           

def _is_character_spaced(text: str) -> bool:
    tokens = text.split()
    if len(tokens) < _MIN_TOKENS:
        return False
    singles = [t for t in tokens if len(t) == 1]
    if len(singles) / len(tokens) < _SINGLE_CHAR_RATIO:
        return False
    letters = sum(1 for t in singles if t.isalpha())
    return letters >= len(singles) * 0.5

def _rejoin_spaced_glyphs(text: str) -> str:
    repaired = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            repaired.append("")
            continue
        words = (w.replace(" ", "") for w in re.split(r" {2,}", stripped))
        repaired.append(" ".join(w for w in words if w))
    return "\n".join(repaired)


# word-per-line pdf issue fix

_WORD_PER_LINE_RATIO = 0.6
_PADDING_LINE_RATIO = 0.25
_MIN_LINES = 10

def _rejoin_word_per_line(text: str) -> str:
    raw_lines = text.split("\n")

    padding = sum(1 for raw in raw_lines if raw != "" and not raw.strip())
    if not raw_lines or padding / len(raw_lines) < _PADDING_LINE_RATIO:
        return text

    lines = []
    for raw in raw_lines:
        if raw == "":
            lines.append("")            
        elif raw.strip():
            lines.append(raw.strip())

    content = [l for l in lines if l]
    if len(content) < _MIN_LINES:
        return text
    if sum(1 for l in content if " " not in l) / len(content) < _WORD_PER_LINE_RATIO:
        return text

    paragraphs, current = [], []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)

def _clean_page_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    if _is_character_spaced(text):
        text = _rejoin_spaced_glyphs(text)
    rejoined = _rejoin_word_per_line(text)
    if rejoined != text:
        rejoined = re.sub(r"[ \t]{2,}", " ", rejoined)
    return rejoined

# Public APIs

def parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [_clean_page_text(page.extract_text() or "") for page in reader.pages]
    return "\n\n".join(pages)

def parse_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def detect_file_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext == "pdf":
        return "pdf"
    if ext in ("md", "markdown"):
        return "md"
    if ext == "txt":
        return "txt"
    raise ValueError(f"Unsupported file type '.{ext}'. Please upload a PDF, TXT or MD file.")

def parse_file(path: Path, file_type: str) -> str:
    text = parse_pdf(path) if file_type == "pdf" else parse_text(path)
    if not text.strip():
        raise ValueError(
            "No readable text found in this file."
        )
    return text