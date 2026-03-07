#!/usr/bin/env python3
"""Optimize images for the web without changing format.

Usage examples:
  python scripts/optimize_images.py --src images --dest images_optimized --quality 85
  python scripts/optimize_images.py --src images --inplace --quality 85
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image
import shutil
import sys


def optimize_image(src: Path, dst: Path, quality: int) -> dict:
    dst.parent.mkdir(parents=True, exist_ok=True)
    info = {"src": str(src), "dst": str(dst), "status": "skipped", "orig_size": 0, "new_size": 0}
    try:
        img = Image.open(src)
    except Exception as e:
        info["status"] = f"error: {e}"
        return info

    fmt = img.format
    info["orig_size"] = src.stat().st_size

    if fmt not in ("JPEG", "PNG", "WEBP", "GIF"):
        # copy unknown formats as-is
        shutil.copy2(src, dst)
        info["status"] = "copied"
        info["new_size"] = dst.stat().st_size
        return info

    save_kwargs = {}
    if fmt == "JPEG":
        if img.mode in ("RGBA", "LA"):
            # JPEG doesn't support alpha; convert preserving background as white
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        exif = img.info.get("exif")
        save_kwargs.update({"quality": quality, "optimize": True, "progressive": True})
        if exif:
            save_kwargs["exif"] = exif
        img.save(dst, "JPEG", **save_kwargs)

    elif fmt == "PNG":
        # Pillow's optimize and compress_level help reduce PNG size.
        save_kwargs.update({"optimize": True, "compress_level": 9})
        # For palette images, keep mode
        img.save(dst, "PNG", **save_kwargs)

    elif fmt == "WEBP":
        save_kwargs.update({"quality": quality, "method": 6})
        img.save(dst, "WEBP", **save_kwargs)

    elif fmt == "GIF":
        # Re-save GIF; Pillow may re-encode frames but keeps GIF format
        img.save(dst, "GIF", save_all=True)

    info["new_size"] = dst.stat().st_size
    info["status"] = "optimized"
    return info


def iter_images(src_dir: Path):
    for p in src_dir.rglob("*"):
        if p.is_file():
            # treat common image extensions
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                yield p


def main(argv=None):
    parser = argparse.ArgumentParser(description="Optimize images for web without changing format")
    parser.add_argument("--src", required=True, help="Source images folder (recursive)")
    parser.add_argument("--dest", help="Destination folder (default: images_optimized)")
    parser.add_argument("--inplace", action="store_true", help="Overwrite original files (dangerous)")
    parser.add_argument("--quality", type=int, default=85, help="JPEG/WEBP quality (1-100), default 85")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files; only show potential savings")
    args = parser.parse_args(argv)

    src = Path(args.src)
    if not src.exists():
        print(f"Source folder not found: {src}")
        sys.exit(2)

    if args.inplace and args.dest:
        print("Cannot use --inplace and --dest together")
        sys.exit(2)

    dest_root = Path(args.dest) if args.dest else (src if args.inplace else Path("images_optimized"))
    if not args.inplace:
        dest_root.mkdir(parents=True, exist_ok=True)

    total_orig = 0
    total_new = 0
    results = []

    for img_path in iter_images(src):
        rel = img_path.relative_to(src)
        dst_path = dest_root.joinpath(rel) if not args.inplace else img_path
        if args.dry_run:
            # perform no-write optimization into a temp location in-memory by calling but then deleting
            temp_dst = dst_path.with_suffix(dst_path.suffix + ".tmp")
            info = optimize_image(img_path, temp_dst, args.quality)
            if temp_dst.exists():
                temp_dst.unlink()
        else:
            info = optimize_image(img_path, dst_path, args.quality)
        results.append(info)
        total_orig += info.get("orig_size", 0) or 0
        total_new += info.get("new_size", 0) or 0

    # Print summary
    saved = total_orig - total_new
    pct = (saved / total_orig * 100) if total_orig else 0
    for r in results:
        s = r["status"]
        if s.startswith("error"):
            print(f"ERR: {r['src']} -> {s}")
        else:
            o = r.get("orig_size", 0)
            n = r.get("new_size", 0)
            if o and n:
                print(f"{r['src']} -> {r['dst']}: {o//1024}KB -> {n//1024}KB")
            else:
                print(f"{r['src']} -> {r['dst']}: {s}")

    print("---")
    print(f"Total: {total_orig//1024}KB -> {total_new//1024}KB, saved {saved//1024}KB ({pct:.1f}%)")


if __name__ == "__main__":
    main()
