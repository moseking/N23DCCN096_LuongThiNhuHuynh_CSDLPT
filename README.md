# Đồ án: Distributed PageRank - Web Page Importance

## 1. Thông tin sinh viên

Lương Thị Như Huỳnh - N23DCCN096 - D23CQCN02-N

## 2. Giới thiệu đề tài

Repository này chứa phần code cho đề tài **#139 Distributed PageRank: Web Page Importance** thuộc môn Cơ sở dữ liệu phân tán.

Project mô phỏng thuật toán PageRank trên đồ thị web, chia dữ liệu cho **4 logical distributed workers**. Chương trình chạy local trên một máy, nhưng mô hình hóa các vấn đề quan trọng của hệ phân tán: graph partitioning, rank swapping, logical message passing, failure detection, network overhead và topology analysis.

Lưu ý: đây là **mô phỏng local của 4 logical workers**, không phải triển khai thật trên 4 máy vật lý.

## 3. Tính năng chính

- Chạy PageRank trên web graph theo mô hình phân tán logic.
- Chia đồ thị cho 4 worker: Node A, Node B, Node C, Node D.
- So sánh 4 chiến lược partitioning: `range`, `random`, `hash`, `degree_aware`.
- Đo edge-cut ratio, worker balance, remote messages và logical network overhead.
- Chạy nhiều tolerance để phân tích convergence rate so với network overhead.
- Mô phỏng lỗi Node B bị down và reassignment partition.
- Thêm multi-model integration ở mức minh họa: join top PageRank pages với metadata CSV mẫu.

## 4. Cấu trúc thư mục

```text
distributed_pagerank.py          # Thuật toán PageRank phân tán và partition metrics
run_experiments.py               # Chạy thí nghiệm so sánh strategy/tolerance
failure_demo.py                  # Demo simulated logical Node B failure
join_top_pages.py                # Join top PageRank pages với metadata CSV mẫu
download_snap_dataset.py         # Tải SNAP Stanford web graph
data/page_metadata_sample.csv    # Metadata mẫu, nhỏ, dùng cho multi-model demo
results/experiment_summary.csv   # Kết quả thí nghiệm dạng CSV
results/experiment_summary.json  # Kết quả thí nghiệm dạng JSON
```

Dataset SNAP thật không nên commit lên GitHub vì file lớn. Sau khi clone repo, có thể tải dataset bằng script trong project.

## 5. Dataset SNAP Stanford

Dataset chính của đồ án là **SNAP Stanford web graph**:

- Source page: <https://snap.stanford.edu/data/web-Stanford.html>
- Direct file: <https://snap.stanford.edu/data/web-Stanford.txt.gz>
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: node là trang web Stanford, directed edge là hyperlink giữa hai trang.

Kịch bản chính của đồ án dùng **100,000 page id đầu tiên** từ SNAP để khớp yêu cầu đề bài. Synthetic dataset chỉ dùng để test nhanh hoặc fallback khi chưa tải dataset thật.

Tải dataset:

```powershell
python download_snap_dataset.py
```

Sau khi tải, file cần nằm ở:

```text
data/web-Stanford.txt.gz
```

## 6. Cài đặt

Project chỉ dùng **Python standard library**, không cần cài package ngoài.

Kiểm tra Python:

```powershell
python --version
```

## 7. Chạy nhanh bằng synthetic dataset

Lệnh này dùng graph giả lập nhỏ để kiểm tra code chạy được ngay:

```powershell
python distributed_pagerank.py --synthetic --nodes 1000 --workers 4
```

Chạy bộ thí nghiệm nhỏ:

```powershell
python run_experiments.py --synthetic --limit-nodes 1000
```

Chạy demo lỗi Node B:

```powershell
python failure_demo.py
```

## 8. Chạy với SNAP Stanford 100k

Chạy PageRank với 100,000 node đầu từ SNAP:

```powershell
python distributed_pagerank.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 100000 --workers 4 --partition-strategy degree_aware --tolerance 1e-6 --max-iterations 100 --out-dir results\snap_web_stanford_100k
```

Chạy toàn bộ thí nghiệm so sánh 4 chiến lược partitioning và 3 tolerance:

```powershell
python run_experiments.py
```

## 9. Graph Partitioning

Project so sánh 4 chiến lược chia đồ thị:

| Strategy | Cách hoạt động | Vai trò trong phân tích |
| --- | --- | --- |
| `range` | Chia các page id thành các đoạn liên tiếp, ví dụ worker 0 giữ nhóm id đầu tiên. | Baseline đơn giản, gần với phân mảnh ngang theo khoảng giá trị. |
| `random` | Gán page vào worker ngẫu nhiên nhưng có seed để tái lập kết quả. | Baseline cho trường hợp partition không biết topology. |
| `hash` | Gán worker bằng công thức `page_id % number_of_workers`. | Cân bằng số node khá tốt nhưng thường cắt nhiều edge. |
| `degree_aware` | Heuristic ưu tiên high-degree nodes, cố gắng đặt node gần neighbor đã được gán và vẫn giữ cân bằng worker. | Không phải METIS, nhưng chứng minh partitioning có xét topology giúp giảm cross-worker communication. |

## 10. Topology Metrics

Project tính các partition-quality metrics sau:

| Metric | Ý nghĩa |
| --- | --- |
| `total_nodes` | Tổng số node được dùng trong scenario. |
| `total_edges` | Tổng số directed edges sau khi lọc theo node limit. |
| `number_of_workers` | Số logical workers. |
| `nodes_per_worker` | Số node của từng worker. |
| `edges_per_worker` | Số outgoing edges bắt đầu từ node thuộc từng worker. |
| `local_edges` | Edge có source và target nằm trong cùng worker. |
| `cross_worker_edges` | Edge có source và target nằm ở hai worker khác nhau. |
| `edge_cut_ratio` | `cross_worker_edges / total_edges`. |
| `active_worker_pairs` | Số cặp worker có trao đổi rank score. |
| `worker_balance_score` | Điểm cân bằng tải giữa các worker, càng gần 1 càng cân bằng. |

Nếu `edge_cut_ratio` cao, nhiều cạnh đi qua ranh giới giữa các worker. Trong Distributed PageRank, mỗi cross-worker edge tạo remote rank-score message, nên edge-cut càng cao thì network overhead càng lớn.

## 11. PageRank và Rank Swapping

Công thức PageRank:

```text
PR(v) = (1 - d) / N + d * sum(PR(u) / out_degree(u))
```

Trong mỗi iteration:

1. Mỗi worker xử lý các node thuộc partition của mình.
2. Nếu edge đi đến node thuộc worker khác, worker nguồn phải gửi rank contribution sang worker đích.
3. Việc trao đổi rank contribution giữa các worker được gọi là **rank swapping**.
4. Sau mỗi iteration, hệ thống tính L1 convergence delta:

```text
delta = sum(abs(new_rank[i] - old_rank[i]))
```

Tolerance càng nhỏ thì điều kiện hội tụ càng chặt, số iteration thường tăng, kéo theo tổng số rank swaps và network overhead tăng.

## 12. Network Overhead Model

Mô hình logical network overhead:

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Trong đó:

- 12 bytes cho mỗi remote rank-score message: 4 bytes page id + 8 bytes rank score.
- 32 bytes header cho mỗi cặp worker có trao đổi dữ liệu trong một iteration.

Đây là overhead logic dùng cho phân tích đồ án. Nếu triển khai thật bằng TCP, HTTP hoặc gRPC, overhead thực tế sẽ cao hơn.

## 13. Kết quả thí nghiệm SNAP 100k

Kết quả dưới đây được sinh từ `python run_experiments.py` với SNAP 100,000 nodes, 4 workers, tolerance `1e-6`.

| Partition strategy | Edge-cut ratio | Worker balance | Iterations | Remote messages | Network MB |
| --- | ---: | ---: | ---: | ---: | ---: |
| `range` | 0.6945 | 0.9791 | 65 | 14,620,190 | 167.34 |
| `random` | 0.7498 | 0.9891 | 65 | 15,784,340 | 180.66 |
| `hash` | 0.7488 | 0.9926 | 65 | 15,764,580 | 180.44 |
| `degree_aware` | 0.0469 | 0.9696 | 65 | 986,310 | 11.31 |

Nhận xét:

- `range`, `random` và `hash` có edge-cut cao nên phát sinh nhiều remote messages.
- `degree_aware` giảm edge-cut rất mạnh, do đó giảm network overhead đáng kể.
- Với cùng tolerance `1e-6`, số iteration giống nhau trong lần chạy này, nhưng network overhead khác nhau do partition quality khác nhau.

## 14. Multi-Model Integration

Để khớp tiêu chí Category 14, project có thêm một lớp multi-model integration ở mức minh họa:

- **Graph model:** edge list web graph từ SNAP hoặc synthetic graph.
- **Relational/document model:** file CSV metadata mẫu `data/page_metadata_sample.csv`.
- **Join logic:** `join_top_pages.py` đọc `pagerank_summary.json`, lấy danh sách `top_pages`, rồi join với metadata theo `page_id`.

Metadata trong `page_metadata_sample.csv` là **sample/synthetic metadata layer**, không phải metadata thật từ SNAP. Mục tiêu là chứng minh project có thể kết hợp kết quả xử lý graph với dữ liệu dạng bảng/document.

Chạy join:

```powershell
python join_top_pages.py
```

Output:

```text
results/top_pages_with_metadata.csv
```

## 15. Failure Demo

Chạy demo lỗi với dataset SNAP:

```powershell
python failure_demo.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 10000 --fail-worker 1 --fail-iteration 3 --max-iterations 6
```

Nếu chưa tải SNAP, chạy demo synthetic:

```powershell
python failure_demo.py --nodes 1000 --max-iterations 5
```

Output cần có:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Lưu ý: đây là **simulated logical node failure**. Node B được đánh dấu DOWN trong simulator, partition 1 được reassigned cho Node A. Đây không phải thao tác kill process thật.

## 16. Rubric Mapping Category 14

| Tiêu chí | Cách project đáp ứng |
| --- | --- |
| Graph Partitioning | So sánh `range`, `random`, `hash`, `degree_aware`; đo edge-cut ratio, active worker pairs và worker balance. |
| Traversal Logic | Cài đặt distributed PageRank iterations, trao đổi rank contribution qua rank swapping. |
| Multi-Model Integration | Join top PageRank pages từ graph model với metadata CSV mẫu theo `page_id`. Đây không phải trọng tâm chính của đề tài #139 nhưng có minh họa rõ. |
| Topology Analysis | Phân tích edge-cut ratio, worker balance, remote messages, network overhead và convergence theo tolerance. |

## 17. File cần nộp

- Code repo: các file `.py`, `README.md`, `data/page_metadata_sample.csv`, `results/experiment_summary.csv`, `results/experiment_summary.json`.
- Project proposal: có thể nộp file Word/PDF riêng.
- 2-page design document: có thể nộp file Word/PDF riêng.
- Analysis report: có thể nộp file Word/PDF riêng.
- Proof video: quay 3-5 phút chạy PageRank và failure demo.

Các file dataset lớn, cache chi tiết và thư mục `__pycache__` không nên commit lên GitHub.
