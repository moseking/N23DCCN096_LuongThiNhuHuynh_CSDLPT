# Báo cáo phân tích theo nguyên lý Cơ sở dữ liệu phân tán

Báo cáo này giải thích thiết kế của đồ án dựa trên các nguyên lý Cơ sở dữ liệu phân tán thường được trình bày bởi Özsu và Valduriez, ví dụ: fragmentation, allocation, local processing, communication cost, intermediate result transfer và failure transparency.

## 1. Dataset và workload

Dataset chính là **SNAP web-Stanford**:

- Source: https://snap.stanford.edu/data/web-Stanford.html
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: node là trang web Stanford, directed edge là hyperlink.
- Kịch bản đồ án: dùng 100,000 page id đầu tiên từ cùng dataset.

PageRank là workload dạng iterative graph analytics. Mỗi iteration duyệt qua các edges và gửi rank contribution từ source page đến target page. Trong góc nhìn Cơ sở dữ liệu phân tán, đây là bài toán xử lý lặp trên dữ liệu đã được phân mảnh.

## 2. Fragmentation và allocation

Fragmentation là quá trình chia dữ liệu tổng thể thành các mảnh nhỏ hơn. Allocation là quyết định mỗi mảnh thuộc về site hoặc worker nào.

Project mô phỏng 4 logical distributed workers:

```text
Node A
Node B
Node C
Node D
```

Với baseline 100,000 nodes, dữ liệu có thể chia theo range:

```text
Node A: pages 0-24,999
Node B: pages 25,000-49,999
Node C: pages 50,000-74,999
Node D: pages 75,000-99,999
```

Tuy nhiên, để phù hợp rubric Category 14, project không chỉ dùng range partitioning mà còn so sánh:

- `random`: chia ngẫu nhiên có seed.
- `hash`: chia theo modulo của page id.
- `degree_aware`: heuristic dựa trên degree và neighbor locality.

Mục tiêu không phải triển khai METIS, mà là chứng minh partitioning ảnh hưởng trực tiếp đến edge-cut ratio và communication overhead.

## 3. Local processing và communication cost

Trong hệ phân tán, chi phí xử lý không chỉ là CPU local. Communication cost thường là yếu tố rất quan trọng.

Trong Distributed PageRank:

- Nếu source và target nằm cùng worker, contribution được xử lý local.
- Nếu source và target nằm ở hai workers khác nhau, contribution phải gửi qua rank swapping.

Rank swapping được xem như việc truyền intermediate results giữa các sites.

Công thức logical network overhead:

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Trong đó:

- `remote_messages`: số rank contribution gửi qua ranh giới worker.
- `active_worker_pairs`: số cặp worker có trao đổi dữ liệu.
- `12 bytes`: gồm 4 bytes page id và 8 bytes rank score.
- `32 bytes`: batch header.

## 4. Topology analysis

Project đo các metric topology:

- `total_nodes`
- `total_edges`
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

Nếu edge-cut ratio cao, nhiều edges đi qua ranh giới worker. Trong PageRank, mỗi cross-worker edge tạo remote rank-score message ở mỗi iteration. Vì vậy edge-cut ratio cao sẽ làm network overhead tăng.

## 5. Analogy với distributed query processing

Trong distributed query processing, hệ thống cố gắng đẩy xử lý xuống local site và chỉ truyền intermediate results khi cần thiết.

Distributed PageRank cũng tương tự:

- Local edges được xử lý ngay tại worker.
- Cross-worker edges tạo intermediate rank contributions.
- Các contributions này được gửi sang worker khác để tạo rank vector mới.

Vì vậy, rank swapping có thể xem như intermediate result transfer trong hệ Cơ sở dữ liệu phân tán.

## 6. Reliability và failure transparency

Project có failure demo cho Node B.

Khi Node B bị mô phỏng down:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Coordinator đánh dấu Node B là `DOWN`, sau đó reassign partition 1 sang Node A. Computation tiếp tục chạy. Đây là mô phỏng failure transparency ở mức đơn giản, chưa phải recovery đầy đủ như checkpoint/log/rollback.

## 7. Kết quả thực nghiệm chính

Kết quả dùng SNAP 100,000 nodes, 4 workers, tolerance `1e-6`:

| Partition strategy | Edge-cut ratio | Worker balance | Iterations | Remote messages | Network MB |
| ------------------ | -------------: | -------------: | ---------: | --------------: | ---------: |
| random             |         0.7498 |         0.9891 |         65 |      15,784,340 |     180.66 |
| hash               |         0.7488 |         0.9926 |         65 |      15,764,580 |     180.44 |
| degree_aware       |         0.0469 |         0.9696 |         65 |         986,310 |      11.31 |

Nhận xét:

- `random` và `hash` có edge-cut ratio khoảng 0.75, nghĩa là phần lớn edges đi qua worker khác.
- `degree_aware` giảm edge-cut ratio xuống 0.0469.
- Khi edge-cut giảm, remote messages và network overhead giảm rất mạnh.

## 8. Trade-off tolerance và overhead

Khi tolerance nhỏ hơn, điều kiện hội tụ chặt hơn. PageRank cần nhiều iteration hơn để L1 delta nhỏ hơn ngưỡng yêu cầu.

Vì mỗi iteration đều có rank swapping:

```text
total_overhead ~= bytes_per_iteration * iterations
```

Do đó:

- Tolerance nhỏ hơn -> nhiều iterations hơn.
- Nhiều iterations hơn -> tổng network overhead cao hơn.
- Edge-cut ratio thấp hơn -> bytes per iteration thấp hơn.

## 9. Mapping với rubric Category 14

| Rubric area             | Project evidence                                                                                                |
| ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| Graph Partitioning      | So sánh `random`, `hash`, `degree_aware`; đo edge-cut ratio, local edges, cross-worker edges và worker balance. |
| Traversal Logic         | Cài đặt iterative distributed PageRank trên graph edges với L1 convergence.                                     |
| Multi-Model Integration | Không phải trọng tâm vì topic #139 là Distributed PageRank, không phải multi-model query.                       |
| Topology Analysis       | Phân tích edge-cut ratio, worker balance, active worker pairs, network overhead, runtime và convergence.        |

## 10. Kết luận

Đồ án cho thấy partitioning ảnh hưởng trực tiếp đến chi phí truyền thông trong Distributed PageRank. Với cùng dataset và cùng tolerance, `degree_aware` giảm edge-cut ratio đáng kể so với `random` và `hash`, từ đó giảm remote messages và network overhead.

Kết quả này phù hợp với nguyên lý Cơ sở dữ liệu phân tán: giảm intermediate result transfer giữa các sites thường giúp giảm communication cost và cải thiện hiệu quả xử lý.

## 11. Tài liệu tham khảo

- M. T. Özsu and P. Valduriez, _Principles of Distributed Database Systems_.
- SNAP Stanford web graph dataset: https://snap.stanford.edu/data/web-Stanford.html
- Saeed K. Rahimi and Frank S. Haug, _Distributed Database Management Systems: A Practical Approach_.
