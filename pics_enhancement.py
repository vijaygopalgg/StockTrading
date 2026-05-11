"""
enhance_photos.py
-----------------
Batch-enhances all JPEGs in INPUT_FOLDER and saves results to OUTPUT_FOLDER.

Enhancements applied per image:
  1. Noise reduction      — OpenCV fastNlMeansDenoisingColored
  2. Auto white balance   — Gray-world algorithm (color balance)
  3. Auto contrast/bright — CLAHE on LAB lightness channel
  4. Sharpening           — Unsharp mask via Pillow

Usage:
  python enhance_photos.py --input /path/to/photos --output /path/to/output

  Optional flags:
    --quality   JPEG save quality 1-95  (default: 92)
    --workers   Parallel threads        (default: 4)
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter


# ── Enhancements ─────────────────────────────────────────────────────────────

def denoise(img_bgr: np.ndarray) -> np.ndarray:
    """Fast non-local means denoising (colored)."""
    return cv2.fastNlMeansDenoisingColored(
        img_bgr,
        None,
        h=6,           # luminance filter strength
        hColor=6,      # color filter strength
        templateWindowSize=7,
        searchWindowSize=21,
    )


def auto_white_balance(img_bgr: np.ndarray) -> np.ndarray:
    """Gray-world white balance: scale each channel so its mean = global mean."""
    result = img_bgr.astype(np.float32)
    mean_b, mean_g, mean_r = (result[:, :, i].mean() for i in range(3))
    global_mean = (mean_b + mean_g + mean_r) / 3
    if mean_b > 0: result[:, :, 0] *= global_mean / mean_b
    if mean_g > 0: result[:, :, 1] *= global_mean / mean_g
    if mean_r > 0: result[:, :, 2] *= global_mean / mean_r
    return np.clip(result, 0, 255).astype(np.uint8)


def auto_contrast(img_bgr: np.ndarray) -> np.ndarray:
    """CLAHE on the L channel of LAB — boosts local contrast without blowout."""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


def sharpen(pil_img: Image.Image) -> Image.Image:
    """Unsharp mask sharpening via Pillow."""
    return pil_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))


# ── Per-image pipeline ────────────────────────────────────────────────────────

def enhance(src: Path, dst: Path, quality: int) -> str:
    try:
        img_bgr = cv2.imread(str(src))
        if img_bgr is None:
            return f"SKIP (unreadable): {src.name}"

        img_bgr = denoise(img_bgr)
        img_bgr = auto_white_balance(img_bgr)
        img_bgr = auto_contrast(img_bgr)

        # Convert to Pillow for sharpening + saving
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img = sharpen(pil_img)

        dst.parent.mkdir(parents=True, exist_ok=True)
        pil_img.save(str(dst), "JPEG", quality=quality, optimize=True)
        return f"OK: {src.name}"

    except Exception as exc:
        return f"ERROR {src.name}: {exc}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch JPEG enhancer")
    parser.add_argument("--input",  default=r"C:\Users\vijay\Pictures\CollegePics\VG_in",  help="Folder with original JPEGs")
    parser.add_argument("--output", default=r"C:\Users\vijay\Pictures\CollegePics\VG_out", help="Folder to save enhanced JPEGs")
    parser.add_argument("--quality", type=int, default=92, help="JPEG output quality (1-95)")
    parser.add_argument("--workers", type=int, default=4,  help="Parallel worker threads")
    args = parser.parse_args()

    input_dir  = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.exists():
        print(f"ERROR: Input folder not found: {input_dir}")
        sys.exit(1)

    jpegs = sorted(
        p for p in input_dir.iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg"}
    )

    if not jpegs:
        print("No JPEG files found in input folder.")
        sys.exit(0)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Found {len(jpegs)} images → saving to {output_dir}")
    print(f"Workers: {args.workers}  |  JPEG quality: {args.quality}\n")

    done = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(enhance, src, output_dir / src.name, args.quality): src
            for src in jpegs
        }
        for future in as_completed(futures):
            msg = future.result()
            done += 1
            if msg.startswith("ERROR"):
                errors += 1
            # Progress line (overwrites in-place)
            print(f"\r[{done}/{len(jpegs)}] {msg:<60}", end="", flush=True)

    print(f"\n\nDone. {done - errors} enhanced, {errors} errors.")


if __name__ == "__main__":
    main()