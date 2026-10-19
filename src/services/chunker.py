import re
from pathlib import Path

from pypdf import PdfReader

PAGE_MARKER = re.compile(r"^\[\[page (\d+)\]\]\s*$", re.MULTILINE)


class Chunker:
    def __init__(self, max_chars: int, overlap: int) -> None:
        self.max_chars = max_chars
        self.overlap = overlap

    def load_pages(self, path: Path) -> list[tuple[int, str]]:
        if path.suffix.lower() == ".pdf":
            return [(i + 1, page.extract_text() or "") for i, page in enumerate(PdfReader(str(path)).pages)]
        text = path.read_text(encoding="utf-8")
        parts = PAGE_MARKER.split(text)
        if len(parts) > 1:
            return [(int(parts[i]), parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)]
        return self._auto_pages(text)

    def _auto_pages(self, text: str, page_chars: int = 2500) -> list[tuple[int, str]]:
        pages, current = [], ""
        for paragraph in re.split(r"\n\s*\n", text):
            if current and len(current) + len(paragraph) > page_chars:
                pages.append(current.strip())
                current = ""
            current += paragraph + "\n\n"
        if current.strip():
            pages.append(current.strip())
        return list(enumerate(pages, start=1))

    def split(self, text: str) -> list[str]:
        text = re.sub(r"[ \t]+", " ", text).strip()
        if len(text) <= self.max_chars:
            return [text] if text else []
        sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        chunks, current = [], ""
        for sentence in sentences:
            if current and len(current) + len(sentence) + 1 > self.max_chars:
                chunks.append(current)
                current = current[-self.overlap :] + " " + sentence
            else:
                current = f"{current} {sentence}".strip()
        if current:
            chunks.append(current)
        return chunks
