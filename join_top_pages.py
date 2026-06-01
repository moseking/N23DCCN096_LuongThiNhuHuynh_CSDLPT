from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


DEFAULT_METADATA = Path("data") / "page_metadata_sample.csv"
DEFAULT_OUTPUT = Path("results") / "top_pages_with_metadata.csv"
DEFAULT_SUMMARY_CANDIDATES = [
    Path("results") / "experiments" / "SNAP web-Stanford_degree_aware_tol_1e-06" / "pagerank_summary.json",
    Path("results") / "experiments" / "synthetic-1000_degree_aware_tol_1e-06" / "pagerank_summary.json",
    Path("results") / "pagerank_summary.json",
]


def find_default_summary() -> Path:
    for candidate in DEFAULT_SUMMARY_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "PageRank summary not found. Run `python run_experiments.py` first, "
        "or pass --pagerank-summary explicitly."
    )


def read_metadata(path: Path) -> dict[int, dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"Metadata file not found: {path}")

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {int(row["page_id"]): row for row in reader}


def read_top_pages(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        raise SystemExit(f"PageRank summary not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    return data.get("top_pages", [])


def join_top_pages(
    pagerank_summary: Path,
    metadata_path: Path,
    output_path: Path,
) -> None:
    metadata = read_metadata(metadata_path)
    top_pages = read_top_pages(pagerank_summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["page_id", "rank", "domain", "page_type", "partition_hint"]
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in top_pages:
            page_id = int(item["page"])
            meta = metadata.get(page_id, {})
            writer.writerow(
                {
                    "page_id": page_id,
                    "rank": item["rank"],
                    "domain": meta.get("domain", "unknown"),
                    "page_type": meta.get("page_type", "unknown"),
                    "partition_hint": meta.get("partition_hint", "unknown"),
                }
            )

    print(f"Read PageRank summary: {pagerank_summary}")
    print(f"Read metadata: {metadata_path}")
    print(f"Wrote joined output: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Join top PageRank pages with sample metadata")
    parser.add_argument("--pagerank-summary", type=Path)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = args.pagerank_summary if args.pagerank_summary else find_default_summary()
    join_top_pages(summary, args.metadata, args.out)


if __name__ == "__main__":
    main()
