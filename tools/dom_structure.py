# tools/dom_structure.py
# Produce a compact DOM outline from saved HTML to help craft stable CSS selectors.
# CLI:
#   python -m tools.dom_structure --file outputs/scraped_content.html --depth 2 --max-children 8

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from bs4 import BeautifulSoup, Tag


def _node_label(el: Tag) -> str:
    """Return tag with id/class markers, e.g., div#main.content.grid"""
    tag = el.name
    _id = (el.get("id") or "").strip()
    _cls = [c for c in (el.get("class") or []) if c]

    out = tag
    if _id:
        out += f"#{_id}"
    if _cls:
        out += "." + ".".join(_cls[:3])  # limit to avoid very long lines
    return out


def _children(el: Tag) -> Iterable[Tag]:
    for child in el.children:
        if isinstance(child, Tag):
            yield child


def dom_outline(html_file: str, depth: int = 2, max_children: int = 8) -> List[str]:
    """
    Return a list of text lines representing a compact DOM outline for the saved HTML.
    """
    html = Path(html_file).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    root = soup.body or soup
    lines: List[str] = []

    def walk(node: Tag, level: int):
        if level > depth:
            return
        kids = list(_children(node))[:max_children]
        for i, k in enumerate(kids):
            indent = "  " * level
            lines.append(f"{indent}- {_node_label(k)}")
            walk(k, level + 1)

    # start from <main> if present; it tends to be semantically relevant
    start = soup.select_one("main") or root
    lines.append(_node_label(start))
    walk(start, 1)
    return lines


def suggest_selectors(html_file: str, max_suggestions: int = 10) -> List[str]:
    """
    Suggest a few potentially-stable selectors for common content areas (main, tables, headings).
    """
    html = Path(html_file).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    suggestions: List[str] = []

    # Common main content area
    for sel in ["main#content", "main", "article", "#content", "#mw-content-text"]:
        if soup.select_one(sel):
            suggestions.append(sel)

    # Typical Wikipedia tables and sections
    for sel in ["table.wikitable", "table.infobox", "div.mw-parser-output h2", "div.mw-parser-output h3"]:
        if soup.select_one(sel):
            suggestions.append(sel)

    # Deduplicate, trim
    out: List[str] = []
    for s in suggestions:
        if s not in out:
            out.append(s)
        if len(out) >= max_suggestions:
            break
    return out


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Print a compact DOM outline and selector suggestions.")
    parser.add_argument("--file", required=True, help="Path to saved HTML file")
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--max-children", type=int, default=8)
    args = parser.parse_args()

    for line in dom_outline(args.file, depth=args.depth, max_children=args.max_children):
        print(line)

    from pprint import pprint
    print("\nSelector suggestions:")
    pprint(suggest_selectors(args.file))
