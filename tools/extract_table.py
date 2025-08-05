# tools/extract_table.py
# HTML extraction helpers using BeautifulSoup.
# Usable as import or CLI:
#   python -m tools.extract_table --file outputs/scraped_content.html --selector "main#content table.wikitable"

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Any, List, Optional

from bs4 import BeautifulSoup


def get_relevant_data(file_name: str, js_selector: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract text content from a saved HTML file with an optional CSS selector.
    Returns:
      {"data": list[str] | str, "count": int?, "selector": str?}
    """
    html = Path(file_name).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    if js_selector:
        elements = soup.select(js_selector)
        return {
            "data": [el.get_text(strip=True) for el in elements],
            "count": len(elements),
            "selector": js_selector,
        }

    return {"data": soup.get_text(separator=" ", strip=True)}


def _table_to_rows(table) -> List[List[str]]:
    """Convert a BeautifulSoup <table> into 2D list of strings."""
    rows = []
    for tr in table.select("tr"):
        cells = tr.find_all(["th", "td"])
        rows.append([c.get_text(strip=True) for c in cells])
    return rows


def extract_first_wikitable_to_csv(html_file: str, csv_out: str) -> Dict[str, Any]:
    """
    Convenience for Wikipedia: find the first .wikitable and write to CSV.
    Returns meta info with row counts and output path.
    """
    html = Path(html_file).read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    tbl = soup.select_one("main#content table.wikitable, table.wikitable")
    if not tbl:
        return {"ok": False, "error": "No .wikitable found"}

    rows = _table_to_rows(tbl)

    out = Path(csv_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow(row)

    return {"ok": True, "rows": len(rows), "file": str(out)}


if __name__ == "__main__":
    import argparse, json

    parser = argparse.ArgumentParser(description="Extract content from saved HTML.")
    parser.add_argument("--file", required=True, help="Path to a saved HTML file")
    parser.add_argument("--selector", help="CSS selector (optional). If omitted, returns full text.")
    parser.add_argument("--wikitable-to", help="If provided, saves the first .wikitable to this CSV path")
    args = parser.parse_args()

    if args.wikitable_to:
        res = extract_first_wikitable_to_csv(args.file, args.wikitable_to)
        print(json.dumps(res, ensure_ascii=False))
    else:
        res = get_relevant_data(args.file, args.selector)
        print(json.dumps(res, ensure_ascii=False))
