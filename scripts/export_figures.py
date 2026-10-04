"""Export source chart PDFs to web images. For manuscript table crops, use export_paper_crops.py.
Requires Pillow, matplotlib and Poppler. No source PDF is modified or copied.
Usage: python scripts/export_figures.py --pdftoppm /path/to/pdftoppm
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static/images/updated"
CACHE = ROOT / ".local-preview/figure-export"

def render(name, poppler):
    source = ROOT / "materials/charts" / (name + ".pdf")
    dest = CACHE / name
    subprocess.run([poppler, "-f", "1", "-singlefile", "-scale-to", "3200",
                    "-png", str(source), str(dest)], check=True)
    return Image.open(dest.with_suffix(".png")).convert("RGB")

def export(im, name, diagram=False):
    ext = ".png" if diagram else ".webp"
    if diagram: im.save(OUT / (name + ext), optimize=True)
    else: im.save(OUT / (name + ext), quality=94, method=6)
    small = im.copy()
    small.thumbnail((1440, 1440))
    if diagram: small.save(OUT / (name + "-small.png"), optimize=True)
    else: small.save(OUT / (name + "-small.webp"), quality=91, method=6)
    return {"file": (name + ext), "width": im.width, "height": im.height,
            "smallWidth": small.width, "smallHeight": small.height}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdftoppm", default=shutil.which("pdftoppm"))
    args = parser.parse_args()
    if not args.pdftoppm: parser.error("Pass --pdftoppm with the Poppler executable path")
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    sources = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
               for f in (ROOT / "materials").rglob("*.pdf")}
    manifest = {}
    teaser = render("teaser", args.pdftoppm)
    # Exclude the lower statistical panels, which conflict with Table III.
    hero = teaser.crop((0, 0, teaser.width, round(teaser.width * .279)))
    manifest["teaser-scene"] = export(hero, "teaser-scene")
    for name in ["overview", "pseudo_loss", "partition_result"]:
        manifest[name] = export(render(name, args.pdftoppm), name, True)
    for name in ["result_airspace", "result_comparison_us3d", "result_comparison_mc_aerial", "result_mc_street"]:
        manifest[name] = export(render(name, args.pdftoppm), name)
    training = render("training_statistics_curve", args.pdftoppm)
    manifest["training-full"] = export(training, "training-full", True)
    manifest["training-resources"] = export(
        training.crop((0, 0, training.width, round(training.height * .49))), "training-resources", True)
    social = Image.new("RGB", (1200, 630), "#f5f8fb")
    draw = ImageDraw.Draw(social)
    fontpath = matplotlib.font_manager.findfont("DejaVu Sans")
    draw.text((52, 54), "BlockGaussian", fill="#152d42", font=ImageFont.truetype(fontpath, 62))
    draw.text((55, 145), "Efficient large-scale novel view synthesis", fill="#486274", font=ImageFont.truetype(fontpath, 27))
    thumb = hero.copy(); thumb.thumbnail((1100, 330))
    social.paste(thumb, ((1200-thumb.width)//2, 245))
    social.save(OUT / "social-preview.png", optimize=True)
    (CACHE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for rel, digest in sources.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest
    (CACHE / "source-sha256.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print("Verified: all source PDFs unchanged.")

if __name__ == "__main__":
    main()
