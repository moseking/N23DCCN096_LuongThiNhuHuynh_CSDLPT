# Distributed Database Project Proposal

Due Date: Week 3

## Project ID & Category

Project ID: **#139**

Category: Distributed Analytics / Distributed Graph Processing

## 1. Project Identity

Team Name: RankSync

Team Members:

- [Your Name]

Project Title: **Distributed PageRank with Rank-Score Swapping Across Four Sites**

## 2. Objective & Problem Statement

### The Why

This project studies a distributed database challenge: iterative analytics over fragmented data can be limited by communication cost. PageRank repeatedly propagates rank scores through a graph. If a link crosses from one site to another, the source site must send a rank-score contribution to the target site.

The core question is:

```text
How does PageRank convergence accuracy affect rank-swapping network overhead?
```

### Core Logic

The project implements PageRank on a web-link graph. The graph is horizontally fragmented across four simulated logical sites. At the end of each iteration, logical nodes exchange remote rank-score contributions. The program records convergence delta, remote messages, total logical network bytes, and iterations until convergence.

## 3. Dataset Specification

Source: SNAP Stanford web graph dataset.

- Source page: https://snap.stanford.edu/data/web-Stanford.html
- Direct file: https://snap.stanford.edu/data/web-Stanford.txt.gz
- Meaning: nodes are Stanford web pages, directed edges are hyperlinks.
- Full dataset: 281,903 nodes and 2,312,497 directed edges.
- Project scenario: first 100,000 page ids from SNAP, matching the assigned 100,000-node topic.

Schema:

```text
source_page_id: integer
target_page_id: integer
```

Fragmentation Strategy:

The 100,000-node scenario is horizontally fragmented by page id:

```text
Node A: page 0 to 24,999
Node B: page 25,000 to 49,999
Node C: page 50,000 to 74,999
Node D: page 75,000 to 99,999
```

Each logical site processes outgoing links for its local pages. If the target page belongs to another site, the contribution is counted as a remote rank-score message.

For Category 14 grading, the implementation also compares `random`, `hash`, and `degree_aware` partitioning. The `degree_aware` heuristic is not METIS, but it is topology-aware: it processes high-degree pages first and tries to keep connected pages near already assigned neighbors. The comparison reports edge-cut ratio, worker balance, local edges, and cross-worker edges.

## 4. System Architecture

Nodes:

Four simulated logical sites: Node A, Node B, Node C, and Node D.

Communication Layer:

Logical message passing inside a Python simulator. This is not a four-machine deployment. Each cross-site link generates a logical rank-score message, and the program estimates bytes transferred per iteration.

Storage:

- Dataset file: `data/web-Stanford.txt.gz`
- Metrics: CSV files under `results/`
- Summaries: JSON files under `results/`

## 5. Tech Stack & Implementation Plan

Programming Language: Python 3

Deployment: Localhost simulation of four logical distributed nodes

Libraries/Frameworks: Python standard library only

Key modules:

- `argparse`
- `csv`
- `gzip`
- `json`
- `random`
- `dataclasses`
- `urllib.request`

## 6. Success Metrics & Analysis

Quantitative Metrics:

- Number of iterations until convergence.
- L1 convergence delta per iteration.
- Edge-cut ratio.
- Worker balance score.
- Local edges and cross-worker edges.
- Remote rank-score messages per iteration.
- Total logical network overhead in bytes and MB.
- Average bytes per iteration.

Failure Scenario:

The proof demo simulates Node B failure during rank swapping. Node B is marked `DOWN`, the coordinator detects a missing heartbeat, and partition 1 is reassigned to Node A. The computation continues and prints cluster state and network metrics.

Command:

```powershell
python failure_demo.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 10000 --fail-worker 1 --fail-iteration 3 --max-iterations 6
```

## 7. Project Milestones

Milestone 1 (Week 5): Dataset download, parser, and four-way fragmentation complete.

Milestone 2 (Week 8): Distributed PageRank core algorithm and rank-swapping metrics operational.

Milestone 3 (Week 12): Failure handling demo, SNAP benchmarking, report, and proof video complete.
