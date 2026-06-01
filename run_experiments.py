from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from distributed_pagerank import (
    PageRankResult,
    build_partition,
    distributed_pagerank,
    generate_web_graph,
    read_edge_list,
    write_metrics_csv,
    write_summary_json,
)


SNAP_DATASET = "SNAP web-Stanford"
DEFAULT_EDGE_LIST = Path("data") / "web-Stanford.txt.gz"
SNAP_FULL_NODE_COUNT = 281_903


def total_remote_messages(result: PageRankResult) -> int:
    return sum(metric.remote_messages for metric in result.metrics)


def total_rank_swaps(result: PageRankResult) -> int:
    """Count worker-to-worker rank-swap batches across all iterations."""
    return sum(metric.active_worker_pairs for metric in result.metrics)


def bytes_per_iteration(result: PageRankResult) -> float:
    if result.iterations == 0:
        return 0.0
    return result.total_network_bytes / result.iterations


def run_one_experiment(
    graph: list[list[int]],
    owners: list[int],
    output_dir: Path,
    worker_count: int,
    damping: float,
    tolerance: float,
    max_iterations: int,
    partition_strategy: str,
) -> tuple[PageRankResult, float]:
    start = time.perf_counter()
    result = distributed_pagerank(
        graph,
        worker_count=worker_count,
        damping=damping,
        tolerance=tolerance,
        max_iterations=max_iterations,
        partition_strategy=partition_strategy,
        owners=owners,
    )
    runtime_seconds = time.perf_counter() - start
    write_metrics_csv(output_dir / "pagerank_metrics.csv", result.metrics)
    write_summary_json(output_dir / "pagerank_summary.json", result)
    return result, runtime_seconds


def build_row(
    result: PageRankResult,
    runtime_seconds: float,
    output_dir: Path,
    dataset: str,
) -> dict[str, object]:
    quality = result.partition_quality
    return {
        "dataset": dataset,
        "node_count": result.node_count,
        "edge_count": result.edge_count,
        "worker_count": result.worker_count,
        "partition_strategy": result.partition_strategy,
        "damping": result.damping,
        "tolerance": result.tolerance,
        "converged": result.converged,
        "iterations_to_converge": result.iterations,
        "total_rank_swaps": total_rank_swaps(result),
        "total_remote_messages": total_remote_messages(result),
        "total_network_bytes": result.total_network_bytes,
        "network_mb": result.total_network_bytes / (1024 * 1024),
        "bytes_per_iteration": bytes_per_iteration(result),
        "runtime_seconds": runtime_seconds,
        "total_nodes": quality.total_nodes,
        "total_edges": quality.total_edges,
        "number_of_workers": quality.number_of_workers,
        "nodes_per_worker": json.dumps(quality.nodes_per_worker),
        "edges_per_worker": json.dumps(quality.edges_per_worker),
        "local_edges": quality.local_edges,
        "cross_worker_edges": quality.cross_worker_edges,
        "edge_cut_ratio": quality.edge_cut_ratio,
        "active_worker_pairs": quality.active_worker_pairs,
        "worker_balance_score": quality.worker_balance_score,
        "out_dir": str(output_dir),
    }


def write_experiment_outputs(output_dir: Path, rows: list[dict[str, object]]) -> None:
    summary_csv = output_dir / "experiment_summary.csv"
    with summary_csv.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary_json = output_dir / "experiment_summary.json"
    with summary_json.open("w", encoding="utf-8") as file:
        json.dump({"experiments": rows}, file, indent=2)

    print(f"Wrote {summary_csv}")
    print(f"Wrote {summary_json}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Distributed PageRank partition experiments")
    parser.add_argument("--synthetic", action="store_true", help="Use a generated graph instead of SNAP data")
    parser.add_argument("--edge-list", type=Path, default=DEFAULT_EDGE_LIST)
    parser.add_argument("--nodes", type=int, default=SNAP_FULL_NODE_COUNT)
    parser.add_argument("--avg-out", type=int, default=10, help="Average out-degree for synthetic graphs")
    parser.add_argument("--seed", type=int, default=42, help="Seed for synthetic graph and random partition")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--damping", type=float, default=0.85)
    parser.add_argument("--max-iterations", type=int, default=100)
    parser.add_argument("--out-dir", type=Path, default=Path("results"))
    parser.add_argument("--tolerances", nargs="+", type=float, default=[1e-4, 1e-5, 1e-6])
    parser.add_argument("--limit-nodes", type=int, default=100_000)
    parser.add_argument(
        "--partition-strategies",
        nargs="+",
        choices=["range", "hash", "random", "degree_aware"],
        default=["range", "random", "hash", "degree_aware"],
    )
    parser.add_argument("--partition-seed", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    partition_seed = args.seed if args.partition_seed is None else args.partition_seed

    if args.synthetic:
        dataset_name = f"synthetic-{args.limit_nodes}"
        print(f"Generating synthetic graph: {args.limit_nodes:,} nodes")
        graph = generate_web_graph(args.limit_nodes, args.avg_out, args.seed)
    else:
        dataset_name = SNAP_DATASET
        if not args.edge_list.exists():
            raise SystemExit(
                f"Dataset file not found: {args.edge_list}\n"
                "Use --synthetic for a quick run, or place web-Stanford.txt.gz in data/."
            )
        print(f"Loading {SNAP_DATASET}: first {args.limit_nodes:,} nodes")
        graph = read_edge_list(
            args.edge_list,
            node_count=args.nodes,
            one_based=True,
            limit_nodes=args.limit_nodes,
        )

    rows: list[dict[str, object]] = []
    for strategy in args.partition_strategies:
        print(f"Building partition: {strategy}")
        owners = build_partition(graph, args.workers, strategy, partition_seed)

        for tolerance in args.tolerances:
            experiment_dir = (
                args.out_dir
                / "experiments"
                / f"{dataset_name}_{strategy}_tol_{tolerance:g}"
            )
            print(f"Running strategy={strategy}, tolerance={tolerance:g}")
            result, runtime_seconds = run_one_experiment(
                graph=graph,
                owners=owners,
                output_dir=experiment_dir,
                worker_count=args.workers,
                damping=args.damping,
                tolerance=tolerance,
                max_iterations=args.max_iterations,
                partition_strategy=strategy,
            )
            rows.append(
                build_row(
                    result=result,
                    runtime_seconds=runtime_seconds,
                    output_dir=experiment_dir,
                    dataset=dataset_name,
                )
            )

    write_experiment_outputs(args.out_dir, rows)


if __name__ == "__main__":
    main()
