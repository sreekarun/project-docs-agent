"""Keyword search over the bundled project docs (project_docs_agent/docs/*.md).

The docs are a snapshot of sreekarun/adk-chatbot's docs/ and README, refreshed
with scripts/sync_docs.sh. They're small (~40 KB), so a plain in-memory index of
markdown sections is enough; no vector store.
"""

import functools
import re
from dataclasses import dataclass
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"
_HEADING = re.compile(r"^(#{1,4})\s+(.*)$")
_WORD = re.compile(r"[a-z0-9_]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "how", "i", "in", "is", "it", "of", "on", "or", "the", "to", "what",
    "when", "where", "which", "why", "with", "we", "you", "my", "our",
}  # fmt: skip


@dataclass(frozen=True)
class Section:
    doc: str
    heading: str
    text: str


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS]


@functools.cache
def sections() -> tuple[Section, ...]:
    """Split every doc into sections at markdown headings."""
    out = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        heading, lines = path.stem, []
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _HEADING.match(line)
            if m:
                if "".join(lines).strip():
                    out.append(Section(path.name, heading, "\n".join(lines).strip()))
                heading, lines = m.group(2).strip(), []
            else:
                lines.append(line)
        if "".join(lines).strip():
            out.append(Section(path.name, heading, "\n".join(lines).strip()))
    return tuple(out)


def search(query: str, limit: int = 5) -> list[tuple[float, Section]]:
    """Rank sections by query-term matches; heading matches count triple."""
    terms = set(_words(query))
    if not terms:
        return []
    scored = []
    for s in sections():
        body, head = _words(s.text), set(_words(s.heading))
        score = sum(body.count(t) for t in terms) + 3 * len(terms & head)
        # Reward covering more distinct terms over repeating one.
        score *= 1 + len(terms & (set(body) | head)) / len(terms)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:limit]
