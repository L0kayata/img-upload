# img-upload

A minimal command-line script to process and upload images to Cloudflare R2.

Each image is uploaded in two versions:
- **Low-res** `photo.webp` — max width 800px (height-proportional for portrait images)
- **High-res** `photo_orig.webp` — max long-edge 3200px

Both versions are converted to WebP.

## Requirements

Python 3.11+

If you haven't **uv** yet, [install uv](https://github.com/astral-sh/uv) or:
```bash
pip install uv
```

Initialize environment:
```bash
uv sync
```

If you don't want to use **uv**, you have to install **Pillow** and **boto3**:
```bash
pip install Pillow boto3
```

## Configuration

Copy the example file and fill in your credentials:
```bash
cp credentials.toml.example credentials.toml
```

Edit `credentials.toml`:
```toml
endpoint_url      = "https://<account_id>.r2.cloudflarestorage.com"
access_key_id     = ""
secret_access_key = ""
bucket_name       = ""
```

## Usage

```
uv run upload.py <source> <r2-dest-dir> [--n]
```

| Argument | Description |
|---|---|
| `source` | Image file or directory (non-recursive) |
| `r2-dest-dir` | Destination prefix in R2 |
| `--n` | Skip upload if the object already exists |

Trailing slashes in `r2-dest-dir` are optional.

### Destination path examples

The destination prefix is used exactly as provided — no source directory name is appended automatically.

```bash
# Upload all images in ./Berlin-1/ to travel/Berlin-1/ in R2
uv run upload.py ./blog-posts/travel/Berlin-1 travel/Berlin-1

# Upload a single file to travel/Berlin-1/ in R2
uv run upload.py ./blog-posts/travel/Berlin-1/IMG_001.jpg travel/Berlin-1

# Upload to a top-level prefix (all files land directly under travel/)
uv run upload.py ./blog-posts/travel/Berlin-1 travel
```

The first form is recommended: the R2 prefix should always reflect the full intended path.

### Skip existing files

```bash
uv run upload.py ./Berlin-1 travel/Berlin-1 --n
```

By default, existing objects are overwritten.

## Output

```
Uploading 2 image(s) → my-bucket/travel/Berlin-1/

IMG_001.jpg
  [ADD]       travel/Berlin-1/IMG_001.webp
  [ADD]       travel/Berlin-1/IMG_001_orig.webp
IMG_002.jpg
  [OVERWRITE] travel/Berlin-1/IMG_002.webp
  [SKIP]      travel/Berlin-1/IMG_002_orig.webp

Done: 3/4 objects uploaded, 1 skipped
```

## Supported formats

`.jpg` `.jpeg` `.png` `.webp` `.heic` `.tiff` `.bmp`

## Roadmap

- Support for other cloud storage providers (AWS S3, Backblaze B2, etc.)
- Configurable resize rules and output quality
- Recursive directory traversal with optional structure preservation