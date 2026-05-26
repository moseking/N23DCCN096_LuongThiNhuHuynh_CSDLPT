from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from distributed_pagerank import generate_web_graph, owner_of, read_edge_list


@dataclass
class WorkerState:
    worker_id: int
    alive: bool = True
    recovered_partitions: list[int] | None = None

    def __post_init__(self) -> None:
        if self.recovered_partitions is None:
            self.recovered_partitions = []


def worker_label(worker_id: int) -> str:
    return chr(ord("A") + worker_id)


def print_cluster_state(workers: list[WorkerState]) -> None:
    status = []
    for worker in workers:
        label = worker_label(worker.worker_id)
        if worker.alive:
            recovered = ""
            if worker.recovered_partitions:
                recovered = f", recovered={worker.recovered_partitions}"
            status.append(f"Node {label}: UP{recovered}")
        else:
            status.append(f"Node {label}: DOWN")
    print("Cluster:", " | ".join(status))


def choose_recovery_worker(workers: list[WorkerState], failed_worker: int) -> int:
    alive_workers = [worker.worker_id for worker in workers if worker.alive and worker.worker_id != failed_worker]
    if not alive_workers:
        raise RuntimeError("No live worker is available for recovery")
    return alive_workers[0]


def simulate_failure_tolerant_pagerank(
    nodes: int,
    average_out_degree: int,
    workers_count: int,
    fail_worker: int,
    fail_iteration: int,
    max_iterations: int,
    damping: float,
    seed: int,
    edge_list: Path | None,
    one_based: bool,
    limit_nodes: int | None,
) -> None:
    if edge_list is None:
        graph = generate_web_graph(nodes, average_out_degree, seed)
        dataset_label = f"synthetic quick-test graph with {nodes:,} pages"
    else:
        graph = read_edge_list(edge_list, nodes, one_based=one_based, limit_nodes=limit_nodes)
        nodes = len(graph)
        dataset_label = f"SNAP edge list {edge_list} with {nodes:,} pages"

    owners = [owner_of(node_id, nodes, workers_count) for node_id in range(nodes)]
    workers = [WorkerState(worker_id=worker_id) for worker_id in range(workers_count)]
    ranks = [1.0 / nodes] * nodes
    base_score = (1.0 - damping) / nodes
    killed = False
    total_network_bytes = 0

    print("Distributed PageRank logical-site failure demo")
    print(f"Dataset: {dataset_label}")
    print(f"Workers: {workers_count} logical sites")
    print(
        f"Failure scenario: mark Node {worker_label(fail_worker)} DOWN at iteration {fail_iteration}"
    )
    print_cluster_state(workers)
    print()

    for iteration in range(1, max_iterations + 1):
        print(f"--- Iteration {iteration} ---")

        if iteration == fail_iteration and not killed:
            workers[fail_worker].alive = False
            killed = True
            print(f"[FAULT] Node {worker_label(fail_worker)} was killed during rank swapping.")
            recovery_worker = choose_recovery_worker(workers, fail_worker)
            workers[recovery_worker].recovered_partitions.append(fail_worker)
            print(
                f"[RECOVERY] Coordinator detected missing heartbeat from Node {worker_label(fail_worker)}."
            )
            print(
                f"[RECOVERY] Partition {fail_worker} reassigned to Node {worker_label(recovery_worker)}."
            )

        dangling_rank = sum(ranks[node] for node, targets in enumerate(graph) if not targets)
        new_ranks = [base_score + damping * dangling_rank / nodes for _ in range(nodes)]
        remote_messages = 0
        active_pairs: set[tuple[int, int]] = set()

        for source, targets in enumerate(graph):
            if not targets:
                continue
            source_owner = owners[source]
            source_runtime_owner = source_owner
            if not workers[source_owner].alive:
                source_runtime_owner = choose_recovery_worker(workers, source_owner)

            contribution = damping * ranks[source] / len(targets)
            for target in targets:
                target_owner = owners[target]
                target_runtime_owner = target_owner
                if not workers[target_owner].alive:
                    target_runtime_owner = choose_recovery_worker(workers, target_owner)

                if source_runtime_owner != target_runtime_owner:
                    remote_messages += 1
                    active_pairs.add((source_runtime_owner, target_runtime_owner))
                new_ranks[target] += contribution

        network_bytes = remote_messages * 12 + len(active_pairs) * 32
        total_network_bytes += network_bytes
        delta = sum(abs(new - old) for new, old in zip(new_ranks, ranks))
        ranks = new_ranks

        print_cluster_state(workers)
        print(f"Remote rank-score messages: {remote_messages:,}")
        print(f"Network overhead this iteration: {network_bytes:,} bytes")
        print(f"Cumulative network overhead: {total_network_bytes:,} bytes")
        print(f"L1 convergence delta: {delta:.8f}")
        print()

    top_pages = sorted(enumerate(ranks), key=lambda item: item[1], reverse=True)[:5]
    print("Demo completed. Top 5 pages after recovery:")
    for page, rank in top_pages:
        print(f"  page={page} rank={rank:.10f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Failure demo for distributed PageRank")
    parser.add_argument("--nodes", type=int, default=5000)
    parser.add_argument("--avg-out", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--fail-worker", type=int, default=1, help="0=A, 1=B, 2=C, 3=D")
    parser.add_argument("--fail-iteration", type=int, default=3)
    parser.add_argument("--max-iterations", type=int, default=8)
    parser.add_argument("--damping", type=float, default=0.85)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--edge-list", type=Path)
    parser.add_argument("--one-based", action="store_true")
    parser.add_argument("--limit-nodes", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    simulate_failure_tolerant_pagerank(
        nodes=args.nodes,
        average_out_degree=args.avg_out,
        workers_count=args.workers,
        fail_worker=args.fail_worker,
        fail_iteration=args.fail_iteration,
        max_iterations=args.max_iterations,
        damping=args.damping,
        seed=args.seed,
        edge_list=args.edge_list,
        one_based=args.one_based,
        limit_nodes=args.limit_nodes,
    )


if __name__ == "__main__":
    main()
