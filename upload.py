#!/usr/bin/env python3
"""
upload.py <source> <r2-dest-dir> [--n]

Processes and uploads images to Cloudflare R2.
- Low-res (embedded): max width 800px (width-constrained)
- High-res (_orig):   max long-edge 3200px

Requires credentials.toml in the same directory as this script.
Dependencies: Pillow, boto3 (Python 3.11+)
"""

import sys
import os
import io
import argparse
import tomllib
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Missing dependency: pip install Pillow")

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    sys.exit("Missing dependency: pip install boto3")


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tiff", ".bmp"}


def load_config() -> dict:
    config_path = Path(__file__).parent / "credentials.toml"
    if not config_path.exists():
        sys.exit(f"credentials.toml not found at: {config_path}")
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    required = ("endpoint_url", "access_key_id", "secret_access_key", "bucket_name")
    missing = [k for k in required if k not in cfg]
    if missing:
        sys.exit(f"Missing keys in credentials.toml: {', '.join(missing)}")
    return cfg


def make_s3_client(cfg: dict):
    return boto3.client(
        "s3",
        endpoint_url=cfg["endpoint_url"],
        aws_access_key_id=cfg["access_key_id"],
        aws_secret_access_key=cfg["secret_access_key"],
    )


def resize_low(img: Image.Image) -> Image.Image:
    """Max width 800px, height proportional. Portrait images are not widened."""
    w, h = img.size
    if w <= 800:
        return img
    new_w = 800
    new_h = int(h * 800 / w)
    return img.resize((new_w, new_h), Image.LANCZOS)


def resize_high(img: Image.Image) -> Image.Image:
    """Max long edge 3200px."""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= 3200:
        return img
    scale = 3200 / long_edge
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def to_webp_bytes(img: Image.Image, quality: int = 85) -> bytes:
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality)
    return buf.getvalue()


def upload_bytes(s3, bucket: str, key: str, data: bytes):
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType="image/webp")


def object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def collect_images(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() in SUPPORTED_EXTENSIONS:
            return [source]
        sys.exit(f"Unsupported file type: {source.suffix}")
    if source.is_dir():
        files = [
            p for p in source.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        if not files:
            sys.exit(f"No supported images found in: {source}")
        return sorted(files)
    sys.exit(f"Source not found: {source}")


def normalize_dest(dest: str) -> str:
    """Ensure dest ends with exactly one slash."""
    return dest.rstrip("/") + "/"


def process_and_upload(
    s3,
    bucket: str,
    image_path: Path,
    dest_prefix: str,
    no_overwrite: bool,
) -> tuple[int, int]:
    """
    Returns (uploaded, skipped) for this image (each image = 2 objects).
    Prints per-file result.
    """
    stem = image_path.stem
    low_key  = f"{dest_prefix}{stem}.webp"
    high_key = f"{dest_prefix}{stem}_orig.webp"

    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"  [ERROR] Cannot open {image_path.name}: {e}")
        return 0, 0

    uploaded = 0
    skipped = 0

    for key, resizer, label in [
        (low_key,  resize_low,  "low"),
        (high_key, resize_high, "orig"),
    ]:
        if no_overwrite and object_exists(s3, bucket, key):
            print(f"  [SKIP]   {key}")
            skipped += 1
            continue

        exists_before = object_exists(s3, bucket, key)
        data = to_webp_bytes(resizer(img))
        try:
            upload_bytes(s3, bucket, key, data)
        except (BotoCoreError, ClientError) as e:
            print(f"  [ERROR] Failed to upload {key}: {e}")
            continue

        action = "OVERWRITE" if exists_before else "ADD"
        print(f"  [{action}] {key}")
        uploaded += 1

    return uploaded, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Upload images to Cloudflare R2 (low-res + orig)."
    )
    parser.add_argument("source", help="Image file or directory")
    parser.add_argument("dest", help="R2 destination prefix, e.g. travel/japan/")
    parser.add_argument("--n", action="store_true", help="Skip existing files")
    args = parser.parse_args()

    cfg = load_config()
    s3 = make_s3_client(cfg)
    bucket = cfg["bucket_name"]

    source = Path(args.source)
    dest_prefix = normalize_dest(args.dest)
    images = collect_images(source)

    total_files = len(images)
    total_uploaded = 0
    total_skipped = 0

    print(f"Uploading {total_files} image(s) → {bucket}/{dest_prefix}\n")

    for img_path in images:
        print(f"{img_path.name}")
        up, sk = process_and_upload(s3, bucket, img_path, dest_prefix, args.n)
        total_uploaded += up
        total_skipped += sk

    total_objects = total_files * 2
    print(f"\nDone: {total_uploaded}/{total_objects} objects uploaded", end="")
    if total_skipped:
        print(f", {total_skipped} skipped", end="")
    print()


if __name__ == "__main__":
    main()
