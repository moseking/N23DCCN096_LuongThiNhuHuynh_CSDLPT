from __future__ import annotations

import argparse
import urllib.request
from pathlib import Path


SNAP_WEB_STANFORD_URL = "https://snap.stanford.edu/data/web-Stanford.txt.gz"
DEFAULT_OUTPUT = Path("data") / "web-Stanford.txt.gz"


def download_dataset(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"Dataset already exists: {output_path}")
        return

    print(f"Downloading SNAP dataset from {url}")
    print(f"Saving to {output_path}")
    urllib.request.urlretrieve(url, output_path)
    print(f"Downloaded {output_path.stat().st_size:,} bytes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download SNAP web-Stanford dataset")
    parser.add_argument("--url", default=SNAP_WEB_STANFORD_URL)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    download_dataset(args.url, args.out)


if __name__ == "__main__":
    main()
