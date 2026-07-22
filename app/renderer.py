from __future__ import annotations
import json
from pathlib import Path
import fitz  # this is PyMuPDF
from . import config

def write_manifest(out_dir: Path, manifest: dict) -> None:
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

def render_pdf_to_pages(pdf_path, out_dir, issue_id, *,
                        school=None, title=None, date=None,
                        dpi=config.DEFAULT_DPI,
                        image_format=config.IMAGE_FORMAT) -> dict:
    doc = fitz.open(pdf_path)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # A matrix scales the page. PDFs are 72 dpi natively, so scale by dpi/72.
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)

    pages, page_width, page_height = [], 0, 0
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix)              # render to a bitmap
        filename = f"page-{index:04d}.{image_format}"     # e.g. page-0001.jpg
        pix.save(pages_dir / filename)                    # write it to disk
        if index == 1:                                    # remember page size
            page_width, page_height = pix.width, pix.height
        pages.append({"index": index, "image": f"pages/{filename}"})
    doc.close()

    manifest = {
        "id": issue_id, "school": school, "title": title, "date": date,
        "page_count": len(pages),
        "page_width": page_width, "page_height": page_height,
        "dpi": dpi, "pages": pages,
    }
    write_manifest(out_dir, manifest)
    return manifest