"""Export unaltered table/figure screenshots from the local manuscript.

Requires Pillow and Poppler. Source PDF remains private and unchanged.
Coordinates refer to the inspected 1314 x 1700 page previews.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "materials/BlockGaussian_IEEE_TIP_R2_supp.pdf"
OUT = ROOT / "static/images/updated"
CACHE = ROOT / ".local-preview/paper-crops"
CROPS = {
    "table-i": (9, (103, 120, 1206, 532)),
    "table-ii": (10, (98, 1157, 651, 1510)),
    "table-iii": (11, (108, 120, 1204, 423)),
    "table-v": (13, (99, 119, 646, 898)),
    "table-vi": (14, (100, 120, 1206, 677)),
    # Keep all chart panels and scene labels, excluding the manuscript caption.
    "figure-8": (12, (99, 117, 1216, 838)),
    "training-gradients": (14, (672, 886, 1210, 1048)),
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdftoppm", default=shutil.which("pdftoppm"))
    args = parser.parse_args()
    if not args.pdftoppm:
        parser.error("Pass --pdftoppm with the Poppler executable path")
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    pages = {}
    manifest = {}
    for name, (number, box) in CROPS.items():
        if number not in pages:
            dest = CACHE / f"page-{number}"
            subprocess.run([args.pdftoppm, "-f", str(number), "-l", str(number),
                            "-singlefile", "-scale-to", "6800", "-png",
                            str(SOURCE), str(dest)], check=True)
            pages[number] = Image.open(dest.with_suffix(".png")).convert("RGB")
        page = pages[number]
        scale = (page.width / 1314, page.height / 1700)
        region = tuple(round(n * scale[i % 2]) for i, n in enumerate(box))
        crop = page.crop(region)
        crop.save(OUT / f"{name}.png", optimize=True)
        preview = crop.copy()
        preview.thumbnail((2200, 2200))
        preview.save(OUT / f"{name}-small.png", optimize=True)
        manifest[name] = {"page": number, "box": box, "size": crop.size,
                          "previewSize": preview.size}
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
    manifest["sourceSHA256"] = digest
    (CACHE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
