# Tài liệu thiết kế 2 trang

## 1. Mục tiêu hệ thống

Đồ án #139 **Distributed PageRank: Web Page Importance** mô phỏng thuật toán PageRank trên đồ thị web trong môi trường phân tán. Hệ thống chạy local trên một máy nhưng mô phỏng **4 logical distributed workers**. Mục tiêu là đo ảnh hưởng của cách chia đồ thị, rank swapping và ngưỡng hội tụ đến network overhead.

Đây không phải triển khai trên 4 máy vật lý. Project tập trung vào các ý chính của Cơ sở dữ liệu phân tán: fragmentation, allocation, communication cost, failure handling và topology analysis.

## 2. Dữ liệu và phân mảnh

Dataset chính là **SNAP Stanford web graph**:

- Source: https://snap.stanford.edu/data/web-Stanford.html
- File local: `data/web-Stanford.txt.gz`
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: node là trang web Stanford, directed edge là hyperlink.

Để khớp đề bài, project dùng 100,000 page id đầu tiên từ SNAP.

Dữ liệu có dạng edge list:

```text
source_page_id target_page_id
```

Baseline chia 100,000 nodes cho 4 logical workers:

```text
Node A: 0-24,999
Node B: 25,000-49,999
Node C: 50,000-74,999
Node D: 75,000-99,999
```

Ngoài cách chia baseline, project so sánh 3 partition strategies:

- `random`: gán page vào worker ngẫu nhiên có seed.
- `hash`: gán worker bằng `page_id % number_of_workers`.
- `degree_aware`: heuristic đơn giản, xử lý high-degree nodes trước, cân bằng worker và cố gắng đặt node gần các neighbor đã được gán.

## 3. Mô hình xử lý PageRank

Công thức PageRank:

```text
PR(v) = (1 - d) / N + d * sum(PR(u) / out_degree(u))
```

Trong đó:

- `d = 0.85` là damping factor.
- `N` là tổng số nodes.
- `u` là các trang có link đến `v`.
- `out_degree(u)` là số link đi ra từ `u`.

Mỗi iteration gồm các bước:

1. Mỗi worker xử lý outgoing edges của các page thuộc partition của mình.
2. Nếu source và target cùng worker, contribution được cộng cục bộ.
3. Nếu source và target khác worker, contribution được tính là remote rank-score message.
4. Sau khi nhận đủ contribution, hệ thống tạo rank vector mới.
5. Tính L1 delta để kiểm tra hội tụ.

Điều kiện hội tụ:

```text
delta = sum(abs(new_rank[i] - old_rank[i]))
```

Thuật toán dừng khi `delta < tolerance` hoặc đạt `max_iterations`.

## 4. Mô hình truyền thông

Chi phí truyền thông chính là **rank swapping** giữa các workers. Mỗi remote rank-score message gồm:

- 4 bytes cho destination page id.
- 8 bytes cho rank score.

Mỗi batch giữa hai workers có thêm 32 bytes header.

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Đây là logical network overhead. Nếu triển khai thật bằng TCP, HTTP hoặc gRPC, overhead thực tế sẽ cao hơn do protocol headers và serialization.

## 5. Topology metrics

Project đo các metric để đánh giá chất lượng partition:

- `total_nodes`
- `total_edges`
- `number_of_workers`
- `nodes_per_worker`
- `edges_per_worker`
- `local_edges`
- `cross_worker_edges`
- `edge_cut_ratio = cross_worker_edges / total_edges`
- `active_worker_pairs`
- `worker_balance_score`

`edge_cut_ratio` là metric quan trọng nhất. Edge-cut càng cao thì càng nhiều edge đi qua ranh giới worker, dẫn đến nhiều rank swapping và network overhead lớn hơn.

## 6. Failure handling

Project có demo lỗi logical Node B. Đây là mô phỏng site failure, không phải kill process thật.

Tại iteration 3:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Sau khi Node B bị đánh dấu `DOWN`, coordinator reassign partition 1 sang Node A và computation tiếp tục chạy.

## 7. Output

Các file kết quả nhỏ nên giữ trong GitHub:

```text
results/experiment_summary.csv
results/experiment_summary.json
```

Các thư mục cache chi tiết như `results/experiments/`, dataset trong `data/`, và file `.gz` không nên commit lên GitHub.

## 8. Hạn chế

- Hệ thống là local simulation, không phải 4 máy vật lý.
- `degree_aware` là heuristic đơn giản, chưa phải thuật toán METIS/Vertex-cut.
- Network overhead là logical overhead, chưa bao gồm overhead thật của TCP/HTTP/gRPC.

Hướng phát triển:

- Triển khai thành 4 process hoặc 4 container.
- Dùng graph partitioning nâng cao hơn.
- Thêm checkpoint/recovery đầy đủ hơn.
