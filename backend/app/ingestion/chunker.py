from typing import List

_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]


def _find_cut(text: str, start: int, end: int, chunk_size: int) -> int:
    """Return a cut position <= end, preferring natural boundaries."""
    window_floor = start + chunk_size // 2
    for sep in _SEPARATORS:
        pos = text.rfind(sep, window_floor, end) #Search for sep between window_floor and end and return the LAST one.
        if pos != -1:
            return pos + len(sep)
    return end #hard-cut if no separator found


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> List[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    n = len(text)
    chunks: List[str] = []
    start = 0

    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            end = _find_cut(text, start, end, chunk_size)

        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break

        next_start = end - overlap
        if next_start <= start:              # safety - always move forward
            next_start = end
        # don't begin the next chunk in the middle of a word
        while 0 < next_start < end and not text[next_start - 1].isspace():
            next_start += 1
        start = next_start

    return chunks

#the code prioritizes Natural boundaries over exact chunk size.