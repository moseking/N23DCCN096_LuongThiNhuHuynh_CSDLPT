# Thông tin sinh viên

Lương Thị Như Huỳnh - N23DCCN096 - D23CQCN02-N

# Distributed PageRank: Web Page Importance

Repository này chứa code cho đề tài **#139 Distributed PageRank: Web Page Importance** thuộc môn Cơ sở dữ liệu phân tán.

Project mô phỏng thuật toán PageRank trên đồ thị web, chia dữ liệu cho **4 logical distributed workers**. Hệ thống chạy local trên một máy, không phải triển khai trên 4 máy vật lý. Mục tiêu chính là đo **network overhead** phát sinh do quá trình **rank swapping** giữa các worker sau mỗi iteration.

## Nội dung chính

Project thực hiện các chức năng:

- Mô phỏng PageRank phân tán trên web graph.
- Chia đồ thị cho 4 logical workers.
- Trao đổi rank score giữa các worker sau mỗi iteration.
- Đo số remote messages và logical network overhead.
- So sánh các chiến lược graph partitioning.
- Phân tích edge-cut ratio, worker balance và convergence.
- Mô phỏng lỗi Node B bị down và gán lại partition.

## Cấu trúc repo

```text
distributed_pagerank.py          # Thuật toán PageRank phân tán và partition metrics
run_experiments.py               # Chạy thí nghiệm so sánh partition/tolerance
failure_demo.py                  # Demo lỗi Node B và recovery logic
README.md                        # Hướng dẫn chạy project
results/experiment_summary.csv   # Kết quả tóm tắt
results/experiment_summary.json  # Kết quả tóm tắt dạng JSON
```

Dataset thật không được commit lên GitHub vì file lớn. Nếu muốn chạy với dataset SNAP, tải file về thư mục `data/`.

## Dataset

Dataset chính dùng trong đồ án là **SNAP Stanford web graph**.

- Source page: https://snap.stanford.edu/data/web-Stanford.html
- Direct file: https://snap.stanford.edu/data/web-Stanford.txt.gz
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: node là trang web Stanford, directed edge là hyperlink giữa hai trang.

Trong thí nghiệm chính, project dùng **100,000 page id đầu tiên** từ dataset SNAP.

Dữ liệu có dạng edge list:

```text
source_page_id target_page_id
```

## Yêu cầu môi trường

Project dùng **Python 3** và chỉ sử dụng Python standard library, không cần cài thêm package ngoài.

Kiểm tra Python:

```powershell
python --version
```

## Chạy nhanh không cần dataset thật

Lệnh sau dùng synthetic graph để kiểm tra project chạy được ngay sau khi clone repo:

```powershell
python distributed_pagerank.py --synthetic --nodes 1000 --workers 4
```

Chạy bộ thí nghiệm nhỏ bằng synthetic graph:

```powershell
python run_experiments.py --synthetic --limit-nodes 1000
```

Chạy demo lỗi Node B bằng synthetic graph:

```powershell
python failure_demo.py
```

## Chạy với dataset SNAP Stanford

Tải file dataset từ SNAP:

```text
web-Stanford.txt.gz
```

Tạo thư mục `data/` trong project và đặt file vào:

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

Nếu chưa có dataset thật, có thể dùng chế độ synthetic để test code.

## Partition strategies

Project so sánh 3 cách chia đồ thị:

| Strategy       | Ý nghĩa                                                                                                          |
| -------------- | ---------------------------------------------------------------------------------------------------------------- |
| `random`       | Gán page vào worker ngẫu nhiên nhưng có seed để kết quả có thể lặp lại.                                          |
| `hash`         | Gán worker bằng công thức `page_id % number_of_workers`.                                                         |
| `degree_aware` | Heuristic đơn giản: ưu tiên high-degree nodes, cân bằng worker và cố gắng đặt node gần các neighbor đã được gán. |

`degree_aware` không phải METIS, nhưng được dùng để chứng minh partitioning tốt hơn có thể giảm cross-worker communication.

## Edge-cut ratio

Edge-cut ratio được tính bằng:

```text
edge_cut_ratio = cross_worker_edges / total_edges
```

Nếu edge-cut ratio cao, nhiều cạnh đi qua ranh giới giữa các worker. Trong Distributed PageRank, mỗi cross-worker edge sẽ tạo remote rank-score message, vì vậy edge-cut càng cao thì network overhead càng lớn.

## Network overhead model

Mỗi remote rank-score message gồm:

- 4 bytes cho destination page id.
- 8 bytes cho PageRank score.

Mỗi batch trao đổi giữa 2 worker có thêm 32 bytes header.

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Đây là logical network overhead. Nếu triển khai thật bằng TCP, HTTP hoặc gRPC, overhead thực tế sẽ cao hơn.

## Kết quả mẫu

Kết quả với SNAP 100,000 nodes, 4 workers, tolerance `1e-6`:

| Partition strategy | Edge-cut ratio | Worker balance | Iterations | Remote messages | Network MB |
| ------------------ | -------------: | -------------: | ---------: | --------------: | ---------: |
| random             |         0.7498 |         0.9891 |         65 |      15,784,340 |     180.66 |
| hash               |         0.7488 |         0.9926 |         65 |      15,764,580 |     180.44 |
| degree_aware       |         0.0469 |         0.9696 |         65 |         986,310 |      11.31 |

Nhận xét: `degree_aware` giảm edge-cut ratio rất mạnh so với `random` và `hash`, nên số remote messages và network overhead cũng giảm đáng kể.

## Demo lỗi Node B

Chạy demo với dataset SNAP:

```powershell
python failure_demo.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 10000 --fail-worker 1 --fail-iteration 3 --max-iterations 6
```

Nếu không có dataset SNAP, chạy demo synthetic:

```powershell
python failure_demo.py
```

Output cần chú ý:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Lưu ý: đây là mô phỏng logical site failure, không phải kill process thật.
