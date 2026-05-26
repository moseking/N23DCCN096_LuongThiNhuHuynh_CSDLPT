from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class IterationMetric:
    iteration: int
    l1_delta: float
    remote_messages: int
    active_worker_pairs: int
    network_bytes: int
    cumulative_network_bytes: int


@dataclass
class PartitionQuality:
    total_nodes: int
    total_edges: int
    number_of_workers: int
    nodes_per_worker: list[int]
    edges_per_worker: list[int]
    local_edges: int
    cross_worker_edges: int
    edge_cut_ratio: float
    active_worker_pairs: int
    worker_balance_score: float


@dataclass
class PageRankResult:
    node_count: int
    edge_count: int
    worker_count: int
    partition_strategy: str
    partition_quality: PartitionQuality
    damping: float
    tolerance: float
    converged: bool
    iterations: int
    total_network_bytes: int
    top_pages: list[tuple[int, float]]
    metrics: list[IterationMetric]


def owner_of(node_id: int, node_count: int, worker_count: int) -> int:
    """Return the logical worker that owns a page id."""
    block_size = (node_count + worker_count - 1) // worker_count
    return min(node_id // block_size, worker_count - 1)


def range_partition(node_count: int, worker_count: int) -> list[int]:
    return [owner_of(node_id, node_count, worker_count) for node_id in range(node_count)]


def hash_partition(node_count: int, worker_count: int) -> list[int]:
    return [node_id % worker_count for node_id in range(node_count)]


def random_partition(node_count: int, worker_count: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    nodes = list(range(node_count))
    rng.shuffle(nodes)
    owners = [0] * node_count
    for index, node_id in enumerate(nodes):
        owners[node_id] = index % worker_count
    return owners


def degree_aware_partition(graph: list[list[int]], worker_count: int) -> list[int]:
    """Greedy heuristic that balances load while keeping neighbors together.

    This is intentionally lightweight, not a METIS replacement. Nodes are
    processed by descending degree. Each node prefers the worker that already
    owns the largest number of its assigned neighbors, while respecting a soft
    node-capacity limit and balancing edge load.
    """
    node_count = len(graph)
    incoming_neighbors: list[list[int]] = [[] for _ in range(node_count)]
    for source, targets in enumerate(graph):
        for target in targets:
            incoming_neighbors[target].append(source)

    degrees = [len(targets) + len(incoming_neighbors[node]) for node, targets in enumerate(graph)]
    node_order = sorted(range(node_count), key=lambda node: degrees[node], reverse=True)
    max_nodes_per_worker = (node_count + worker_count - 1) // worker_count
    owners = [-1] * node_count
    node_load = [0] * worker_count
    edge_load = [0] * worker_count

    for node in node_order:
        affinity = [0] * worker_count
        for neighbor in graph[node]:
            owner = owners[neighbor]
            if owner != -1:
                affinity[owner] += 1
        for neighbor in incoming_neighbors[node]:
            owner = owners[neighbor]
            if owner != -1:
                affinity[owner] += 1

        candidates = [
            worker
            for worker in range(worker_count)
            if node_load[worker] < max_nodes_per_worker
        ]
        if not candidates:
            candidates = list(range(worker_count))

        best_worker = min(
            candidates,
            key=lambda worker: (
                -affinity[worker],
                edge_load[worker],
                node_load[worker],
                worker,
            ),
        )
        owners[node] = best_worker
        node_load[best_worker] += 1
        edge_load[best_worker] += len(graph[node])

    return owners


def build_partition(
    graph: list[list[int]],
    worker_count: int,
    strategy: str,
    seed: int = 42,
) -> list[int]:
    node_count = len(graph)
    if strategy == "range":
        return range_partition(node_count, worker_count)
    if strategy == "hash":
        return hash_partition(node_count, worker_count)
    if strategy == "random":
        return random_partition(node_count, worker_count, seed)
    if strategy == "degree_aware":
        return degree_aware_partition(graph, worker_count)
    raise ValueError(f"Unknown partition strategy: {strategy}")


def worker_balance_score(nodes_per_worker: list[int], edges_per_worker: list[int]) -> float:
    """Return a 0..1 balance score, where 1 means perfectly balanced."""
    def ratio(values: list[int]) -> float:
        maximum = max(values) if values else 0
        minimum = min(values) if values else 0
        if maximum == 0:
            return 1.0
        return minimum / maximum

    return (ratio(nodes_per_worker) + ratio(edges_per_worker)) / 2


def analyze_partition(graph: list[list[int]], owners: list[int], worker_count: int) -> PartitionQuality:
    total_nodes = len(graph)
    total_edges = count_edges(graph)
    nodes_per_worker = [0] * worker_count
    edges_per_worker = [0] * worker_count
    local_edges = 0
    cross_worker_edges = 0
    active_pairs: set[tuple[int, int]] = set()

    for node, owner in enumerate(owners):
        nodes_per_worker[owner] += 1
        edges_per_worker[owner] += len(graph[node])
        for target in graph[node]:
            target_owner = owners[target]
            if owner == target_owner:
                local_edges += 1
            else:
                cross_worker_edges += 1
                active_pairs.add((owner, target_owner))

    edge_cut_ratio = cross_worker_edges / total_edges if total_edges else 0.0
    return PartitionQuality(
        total_nodes=total_nodes,
        total_edges=total_edges,
        number_of_workers=worker_count,
        nodes_per_worker=nodes_per_worker,
        edges_per_worker=edges_per_worker,
        local_edges=local_edges,
        cross_worker_edges=cross_worker_edges,
        edge_cut_ratio=edge_cut_ratio,
        active_worker_pairs=len(active_pairs),
        worker_balance_score=worker_balance_score(nodes_per_worker, edges_per_worker),
    )


def generate_web_graph(
    node_count: int,
    average_out_degree: int,
    seed: int,
    dangling_rate: float = 0.02,
) -> list[list[int]]:
    """Generate a deterministic synthetic graph for quick tests only."""
    rng = random.Random(seed)
    max_degree = max(1, average_out_degree * 2)
    graph: list[list[int]] = []

    for source in range(node_count):
        if rng.random() < dangling_rate:
            graph.append([])
            continue

        degree = rng.randint(1, max_degree)
        targets: set[int] = set()
        while len(targets) < degree:
            target = rng.randrange(node_count)
            if target != source:
                targets.add(target)
        graph.append(sorted(targets))

    return graph


def read_edge_list(
    path: Path,
    node_count: int | None = None,
    one_based: bool = False,
    limit_nodes: int | None = None,
) -> list[list[int]]:
    """Read an edge-list dataset with lines in the form: source target."""
    edges: list[tuple[int, int]] = []
    max_node = -1

    open_file = gzip.open if path.suffix == ".gz" else open
    with open_file(path, "rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.replace(",", " ").split()
            if len(parts) != 2:
                raise ValueError(f"Invalid edge list at line {line_number}: {line!r}")
            source, target = int(parts[0]), int(parts[1])
            if one_based:
                source -= 1
                target -= 1
            if source < 0 or target < 0:
                raise ValueError(f"Negative node id at line {line_number}")
            if limit_nodes is not None and (source >= limit_nodes or target >= limit_nodes):
                continue
            edges.append((source, target))
            max_node = max(max_node, source, target)

    final_node_count = limit_nodes if limit_nodes is not None else node_count
    if final_node_count is None:
        final_node_count = max_node + 1
    if final_node_count <= max_node:
        raise ValueError("node_count is smaller than the largest node id in the dataset")

    graph = [[] for _ in range(final_node_count)]
    for source, target in edges:
        if source != target:
            graph[source].append(target)

    for source in range(final_node_count):
        graph[source] = sorted(set(graph[source]))

    return graph


def count_edges(graph: Iterable[list[int]]) -> int:
    return sum(len(targets) for targets in graph)


def estimate_message_bytes(remote_messages: int, active_worker_pairs: int) -> int:
    """Estimate traffic for rank-score swapping.

    Each remote contribution carries a destination page id and a rank score:
    4 bytes for an int32 page id + 8 bytes for a float64 score. Each non-empty
    worker-to-worker batch also pays a small 32-byte header.
    """
    payload_bytes = remote_messages * (4 + 8)
    batch_header_bytes = active_worker_pairs * 32
    return payload_bytes + batch_header_bytes


def distributed_pagerank(
    graph: list[list[int]],
    worker_count: int = 4,
    damping: float = 0.85,
    tolerance: float = 1e-6,
    max_iterations: int = 100,
    top_k: int = 10,
    partition_strategy: str = "range",
    owners: list[int] | None = None,
    partition_seed: int = 42,
) -> PageRankResult:
    node_count = len(graph)
    if node_count == 0:
        raise ValueError("graph must contain at least one node")

    edge_count = count_edges(graph)
    if owners is None:
        owners = build_partition(graph, worker_count, partition_strategy, partition_seed)
    if len(owners) != node_count:
        raise ValueError("owners length must match the graph node count")
    partition_quality = analyze_partition(graph, owners, worker_count)
    ranks = [1.0 / node_count] * node_count
    base_score = (1.0 - damping) / node_count
    metrics: list[IterationMetric] = []
    total_network_bytes = 0
    converged = False

    for iteration in range(1, max_iterations + 1):
        dangling_rank = sum(ranks[node] for node, targets in enumerate(graph) if not targets)
        new_ranks = [base_score + damping * dangling_rank / node_count for _ in range(node_count)]
        remote_messages = 0
        active_pairs: set[tuple[int, int]] = set()

        for source, targets in enumerate(graph):
            if not targets:
                continue
            source_owner = owners[source]
            contribution = damping * ranks[source] / len(targets)

            for target in targets:
                target_owner = owners[target]
                if source_owner != target_owner:
                    remote_messages += 1
                    active_pairs.add((source_owner, target_owner))
                new_ranks[target] += contribution

        l1_delta = sum(abs(new - old) for new, old in zip(new_ranks, ranks))
        network_bytes = estimate_message_bytes(remote_messages, len(active_pairs))
        total_network_bytes += network_bytes
        metrics.append(
            IterationMetric(
                iteration=iteration,
                l1_delta=l1_delta,
                remote_messages=remote_messages,
                active_worker_pairs=len(active_pairs),
                network_bytes=network_bytes,
                cumulative_network_bytes=total_network_bytes,
            )
        )
        ranks = new_ranks

        if l1_delta < tolerance:
            converged = True
            break

    top_pages = sorted(enumerate(ranks), key=lambda item: item[1], reverse=True)[:top_k]
    return PageRankResult(
        node_count=node_count,
        edge_count=edge_count,
        worker_count=worker_count,
        partition_strategy=partition_strategy,
        partition_quality=partition_quality,
        damping=damping,
        tolerance=tolerance,
        converged=converged,
        iterations=len(metrics),
        total_network_bytes=total_network_bytes,
        top_pages=top_pages,
        metrics=metrics,
    )


def write_metrics_csv(path: Path, metrics: list[IterationMetric]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "iteration",
                "l1_delta",
                "remote_messages",
                "active_worker_pairs",
                "network_bytes",
                "cumulative_network_bytes",
            ],
        )
        writer.writeheader()
        for metric in metrics:
            writer.writerow(asdict(metric))


def write_summary_json(path: Path, result: PageRankResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(result)
    data["top_pages"] = [{"page": page, "rank": rank} for page, rank in result.top_pages]
    data["metrics"] = [asdict(metric) for metric in result.metrics]
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Distributed PageRank simulator for 4 logical nodes")
    dataset = parser.add_mutually_exclusive_group()
    dataset.add_argument("--edge-list", type=Path, help="Path to an edge-list file: source target")
    dataset.add_argument("--synthetic", action="store_true", help="Generate a synthetic graph")
    parser.add_argument("--nodes", type=int, default=100_000, help="Number of pages/nodes")
    parser.add_argument("--one-based", action="store_true", help="Treat edge-list node ids as 1-based")
    parser.add_argument("--limit-nodes", type=int, help="Use only edges whose endpoints are below this node count")
    parser.add_argument("--avg-out", type=int, default=10, help="Average synthetic out-degree")
    parser.add_argument("--workers", type=int, default=4, help="Number of distributed workers")
    parser.add_argument(
        "--partition-strategy",
        choices=["range", "hash", "random", "degree_aware"],
        default="range",
        help="Logical graph partitioning strategy",
    )
    parser.add_argument("--partition-seed", type=int, default=42, help="Seed for random partitioning")
    parser.add_argument("--damping", type=float, default=0.85, help="PageRank damping factor")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="Convergence threshold by L1 delta")
    parser.add_argument("--max-iterations", type=int, default=100, help="Maximum number of iterations")
    parser.add_argument("--seed", type=int, default=42, help="Synthetic graph random seed")
    parser.add_argument("--out-dir", type=Path, default=Path("results"), help="Output directory")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.edge_list:
        if not args.edge_list.exists():
            raise SystemExit(
                f"Dataset file not found: {args.edge_list}\n"
                "Use --synthetic for a quick run, or place web-Stanford.txt.gz in data/."
            )
        graph = read_edge_list(args.edge_list, args.nodes, args.one_based, args.limit_nodes)
    else:
        graph = generate_web_graph(args.nodes, args.avg_out, args.seed)

    result = distributed_pagerank(
        graph,
        worker_count=args.workers,
        damping=args.damping,
        tolerance=args.tolerance,
        max_iterations=args.max_iterations,
        partition_strategy=args.partition_strategy,
        partition_seed=args.partition_seed,
    )

    metrics_path = args.out_dir / "pagerank_metrics.csv"
    summary_path = args.out_dir / "pagerank_summary.json"
    write_metrics_csv(metrics_path, result.metrics)
    write_summary_json(summary_path, result)

    print(f"Nodes: {result.node_count:,}")
    print(f"Edges: {result.edge_count:,}")
    print(f"Workers: {result.worker_count}")
    print(f"Partition strategy: {result.partition_strategy}")
    print(f"Cross-worker edges: {result.partition_quality.cross_worker_edges:,}")
    print(f"Edge-cut ratio: {result.partition_quality.edge_cut_ratio:.4f}")
    print(f"Worker balance score: {result.partition_quality.worker_balance_score:.4f}")
    print(f"Converged: {result.converged}")
    print(f"Iterations: {result.iterations}")
    print(f"Total network overhead: {result.total_network_bytes:,} bytes")
    print(f"Network overhead MB: {result.total_network_bytes / (1024 * 1024):.2f}")
    print("Top pages:")
    for page, rank in result.top_pages:
        print(f"  page={page} rank={rank:.10f}")
    print(f"CSV metrics: {metrics_path}")
    print(f"JSON summary: {summary_path}")


if __name__ == "__main__":
    main()
