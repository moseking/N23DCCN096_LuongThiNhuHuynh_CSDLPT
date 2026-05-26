# Đồ án: Distributed PageRank - Web Page Importance

## 1. Giới thiệu đề tài

Đề tài #139 yêu cầu cài đặt thuật toán PageRank trên một `Web_Link_Graph`, chạy trên 4 node phân tán, các node trao đổi rank score sau mỗi vòng lặp, sau đó phân tích convergence rate so với network overhead.

Trong đồ án này, hệ thống được xây dựng dưới dạng **mô phỏng local 4 logical distributed workers**. Nghĩa là chương trình chạy trên một máy, nhưng bên trong mô phỏng 4 worker logic: Node A, Node B, Node C và Node D.

Mục tiêu chính của project:

- Chia đồ thị web cho nhiều worker.
- Mô phỏng trao đổi rank score giữa các worker.
- Đo network overhead do rank swapping.
- So sánh các chiến lược graph partitioning.
- Phân tích edge-cut ratio, worker balance và convergence.
- Mô phỏng lỗi Node B bị down và reassign partition.

## 2. Dataset SNAP Stanford

Dataset chính là **SNAP Stanford web graph**:

- Source page: https://snap.stanford.edu/data/web-Stanford.html
- Direct file: https://snap.stanford.edu/data/web-Stanford.txt.gz
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: mỗi node là một trang web Stanford, mỗi directed edge là một hyperlink giữa hai trang.

Để khớp với yêu cầu đề bài, project dùng 100,000 page id đầu tiên từ dataset SNAP. Synthetic dataset chỉ được giữ làm chế độ chạy nhanh hoặc fallback, không phải kết quả chính của báo cáo.

## 3. Cơ sở lý thuyết PageRank

PageRank đánh giá độ quan trọng của trang web dựa trên cấu trúc liên kết. Nếu trang A trỏ đến trang B, A truyền một phần điểm quan trọng của nó cho B.

Công thức PageRank:

```text
PR(v) = (1 - d) / N + d * sum(PR(u) / out_degree(u))
```

Trong đó:

- `PR(v)`: điểm PageRank của trang `v`.
- `d`: damping factor, mặc định là `0.85`.
- `N`: tổng số trang.
- `u`: các trang có link trỏ đến `v`.
- `out_degree(u)`: số link đi ra từ `u`.

Điều kiện hội tụ được đo bằng L1 delta:

```text
delta = sum(abs(new_rank[i] - old_rank[i]))
```

Khi `delta < tolerance`, thuật toán được xem là hội tụ.

## 4. Thiết kế hệ phân tán 4 logical workers

Với kịch bản 100,000 node, baseline ban đầu có thể chia theo page id:

```text
Node A: 0-24,999
Node B: 25,000-49,999
Node C: 50,000-74,999
Node D: 75,000-99,999
```

Mỗi logical worker xử lý các outgoing edges của những page mà nó sở hữu.

- Nếu source và target nằm cùng worker, rank contribution được cộng cục bộ.
- Nếu source và target nằm ở hai worker khác nhau, contribution được xem là remote rank-score message.

Luồng xử lý mỗi iteration:

1. Mỗi worker đọc rank hiện tại của các page trong partition của mình.
2. Worker tính rank contribution theo các outgoing links.
3. Contribution cục bộ được cộng trực tiếp.
4. Contribution đến worker khác được tính là rank swapping.
5. Hệ thống tạo rank vector mới.
6. Tính L1 delta để kiểm tra hội tụ.

## 5. Graph partitioning

Project so sánh 3 chiến lược chia đồ thị:

| Strategy       | Ý nghĩa                                                                                                              |
| -------------- | -------------------------------------------------------------------------------------------------------------------- |
| `random`       | Gán page vào worker ngẫu nhiên, có seed để kết quả lặp lại được.                                                     |
| `hash`         | Gán worker bằng công thức `page_id % number_of_workers`.                                                             |
| `degree_aware` | Heuristic đơn giản: xử lý high-degree nodes trước, cân bằng worker và cố gắng đặt node gần các neighbor đã được gán. |

Mục tiêu không phải triển khai METIS hay Vertex-cut đầy đủ. Mục tiêu là chứng minh rằng cách chia đồ thị ảnh hưởng trực tiếp đến edge-cut ratio và network overhead.

## 6. Topology analysis

Project đo các metric sau:

- `total_nodes`
- `total_edges`
- `number_of_workers`
- `nodes_per_worker`
- `edges_per_worker`
- `local_edges`
- `cross_worker_edges`
- `edge_cut_ratio`
- `active_worker_pairs`
- `worker_balance_score`

Metric quan trọng nhất là:

```text
edge_cut_ratio = cross_worker_edges / total_edges
```

Nếu edge-cut ratio cao, nhiều cạnh đi qua ranh giới giữa các worker. Trong Distributed PageRank, mỗi cross-worker edge sẽ tạo remote rank-score message ở mỗi iteration. Vì vậy edge-cut ratio càng cao thì network overhead càng lớn.

## 7. Mô hình network overhead

Mỗi remote rank-score message gồm:

- `4 bytes`: destination page id.
- `8 bytes`: rank score dạng float64.

Mỗi batch trao đổi giữa hai worker có thêm `32 bytes` header.

Công thức:

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Đây là **logical network overhead**. Nếu triển khai thật bằng TCP, HTTP hoặc gRPC, overhead thực tế sẽ cao hơn do protocol headers, serialization metadata và chi phí mạng thật.

## 8. Cài đặt và lệnh chạy

Chạy nhanh bằng synthetic data, không cần dataset thật:

```powershell
python distributed_pagerank.py --synthetic --nodes 1000 --workers 4
```

Chạy bộ thí nghiệm nhỏ bằng synthetic data:

```powershell
python run_experiments.py --synthetic --limit-nodes 1000
```

Nếu muốn chạy với dataset SNAP thật, tải file `web-Stanford.txt.gz` từ SNAP và đặt tại:

```text
data/web-Stanford.txt.gz
```

Chạy PageRank với 100,000 node đầu từ SNAP:

```powershell
python distributed_pagerank.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 100000 --workers 4 --partition-strategy degree_aware --tolerance 1e-6 --max-iterations 100 --out-dir results\snap_web_stanford_100k
```

Chạy toàn bộ thí nghiệm chính:

```powershell
python run_experiments.py
```

Chạy failure demo:

```powershell
python failure_demo.py
```

## 9. Kết quả thực nghiệm

Kết quả SNAP 100,000 nodes, 4 workers, tolerance `1e-6`:

| Partition strategy | Edge-cut ratio | Worker balance | Iterations | Remote messages | Network MB |
| ------------------ | -------------: | -------------: | ---------: | --------------: | ---------: |
| random             |         0.7498 |         0.9891 |         65 |      15,784,340 |     180.66 |
| hash               |         0.7488 |         0.9926 |         65 |      15,764,580 |     180.44 |
| degree_aware       |         0.0469 |         0.9696 |         65 |         986,310 |      11.31 |

Nhận xét:

- `random` và `hash` có edge-cut ratio khoảng 0.75, nghĩa là phần lớn edges đi qua worker khác.
- `degree_aware` giảm edge-cut ratio xuống 0.0469.
- Khi edge-cut giảm, số remote messages và network overhead giảm rất mạnh.

## 10. Phân tích tolerance và overhead

Khi tolerance nhỏ hơn, điều kiện hội tụ chặt hơn. PageRank cần nhiều iteration hơn để L1 delta giảm xuống dưới ngưỡng yêu cầu.

Vì mỗi iteration đều có rank swapping:

```text
total_network_overhead ~= bytes_per_iteration * iterations
```

Do đó:

- Tolerance nhỏ hơn dẫn đến nhiều iterations hơn.
- Nhiều iterations hơn làm tổng network overhead cao hơn.
- Edge-cut ratio thấp hơn làm bytes per iteration thấp hơn.

## 11. Failure demo

Failure demo là mô phỏng logical site failure, không phải kill process thật.

Ở iteration 3, Node B được đánh dấu `DOWN`. Coordinator phát hiện missing heartbeat và reassign partition 1 sang Node A.

Ba dòng quan trọng trong output:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Sau failure, chương trình vẫn tiếp tục in cluster state, remote messages, network overhead và L1 convergence delta.

## 12. Mapping với rubric Category 14

| Rubric area             | Evidence trong project                                                                                          |
| ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| Graph Partitioning      | So sánh `random`, `hash`, `degree_aware`; đo edge-cut ratio, local edges, cross-worker edges và worker balance. |
| Traversal Logic         | Cài đặt distributed iterative PageRank trên graph edges, có L1 convergence.                                     |
| Multi-Model Integration | Không phải trọng tâm vì topic #139 là Distributed PageRank, không phải multi-model query.                       |
| Topology Analysis       | Phân tích edge-cut ratio, worker balance, active worker pairs, network overhead, runtime và convergence.        |

## 13. Hạn chế và hướng phát triển

Hạn chế:

- Hệ thống hiện tại là local simulation, không phải 4 máy vật lý.
- Network overhead là logical overhead, chưa bao gồm overhead thật của TCP/HTTP/gRPC.
- `degree_aware` là heuristic đơn giản, chưa phải METIS hoặc Vertex-cut đầy đủ.

Hướng phát triển:

- Triển khai thành 4 process hoặc 4 container.
- Dùng graph partitioning nâng cao hơn.
- Thêm checkpoint/recovery đầy đủ hơn.
- Nén message hoặc gộp batch để giảm traffic.
