#!/usr/bin/env python3
"""Render the Spanish HTML manual to PDF and record its source checksum."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, default=ROOT / "docs" / "manual.html")
    parser.add_argument("--pdf", type=Path, default=ROOT / "docs" / "manual.pdf")
    parser.add_argument(
        "--checksum", type=Path, default=ROOT / "docs" / "manual.sha256"
    )
    args = parser.parse_args()

    try:
        from weasyprint import HTML
    except ImportError as error:
        raise SystemExit(
            "Falta WeasyPrint. Instálelo con: python3 -m pip install weasyprint"
        ) from error

    html = args.html.resolve()
    if not html.is_file():
        raise SystemExit(f"No existe el manual HTML: {html}")
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    HTML(filename=str(html), base_url=str(html.parent)).write_pdf(str(args.pdf))
    digest = hashlib.sha256(html.read_bytes()).hexdigest()
    args.checksum.write_text(f"{digest}  {html.name}\n", encoding="ascii")
    print(args.pdf)
    print(args.checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
