# Đồ án Distributed PageRank: Web Page Importance

Đây là repository code cho đề tài **#139 Distributed PageRank: Web Page Importance** trong môn Cơ sở dữ liệu phân tán.

Project mô phỏng thuật toán PageRank trên đồ thị web, chia dữ liệu cho **4 logical distributed workers**. Đây là mô phỏng chạy local trên một máy, không phải triển khai trên 4 máy vật lý. Mục tiêu chính là thể hiện:

- Chia dữ liệu đồ thị cho nhiều worker.
- Trao đổi rank score giữa các worker sau mỗi iteration.
- Đo network overhead do rank swapping.
- So sánh chất lượng graph partitioning.
- Phân tích edge-cut ratio, worker balance và convergence.
- Mô phỏng lỗi Node B bị down và reassign partition.

## File chính trong repo

```text
distributed_pagerank.py          # Thuật toán PageRank + partition metrics
run_experiments.py               # Chạy thí nghiệm so sánh partition/tolerance
failure_demo.py                  # Demo Node B failure
README.md                        # Hướng dẫn chạy project
BAO_CAO_DO_AN.md                 # Báo cáo tiếng Việt dạng Markdown
ANALYSIS_OZSU_VALDURIEZ.md       # Analysis theo lý thuyết Özsu & Valduriez
PROJECT_PROPOSAL.md              # Proposal theo template
DESIGN_DOCUMENT_2_PAGE.md        # Design document 2 trang
results/experiment_summary.csv   # Kết quả tóm tắt
results/experiment_summary.json  # Kết quả tóm tắt dạng JSON
```

Dataset thật không được commit lên GitHub vì file lớn. Nếu muốn chạy với SNAP, tải dataset về thư mục `data/`.

## Chạy nhanh không cần dataset thật

Lệnh này dùng synthetic graph để kiểm tra project chạy được ngay sau khi clone repo:

```powershell
python distributed_pagerank.py --synthetic --nodes 1000 --workers 4
```

Chạy bộ thí nghiệm nhỏ bằng synthetic graph:

```powershell
python run_experiments.py --synthetic --limit-nodes 1000
```

Chạy demo lỗi logical Node B:

```powershell
python failure_demo.py
```

## Chạy với dataset SNAP Stanford

Dataset chính dùng trong đồ án là **SNAP Stanford web graph**:

- Source page: https://snap.stanford.edu/data/web-Stanford.html
- Direct file: https://snap.stanford.edu/data/web-Stanford.txt.gz
- Full dataset: 281,903 nodes và 2,312,497 directed edges.
- Ý nghĩa: node là trang web Stanford, directed edge là hyperlink.

Cách chuẩn bị:

1. Tải file `web-Stanford.txt.gz` từ SNAP.
2. Tạo thư mục `data/` trong project.
3. Đặt file tại:

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

Nếu thiếu dataset thật, chương trình sẽ báo lỗi thân thiện và gợi ý dùng `--synthetic` hoặc đặt file `web-Stanford.txt.gz` vào thư mục `data/`.

## Partition strategies

Project so sánh 3 cách chia đồ thị:

| Strategy       | Ý nghĩa                                                                                                              |
| -------------- | -------------------------------------------------------------------------------------------------------------------- |
| `random`       | Gán page vào worker ngẫu nhiên nhưng có seed để lặp lại được.                                                        |
| `hash`         | Gán worker bằng `page_id % number_of_workers`.                                                                       |
| `degree_aware` | Heuristic đơn giản: xử lý high-degree nodes trước, cân bằng worker và cố gắng đặt node gần các neighbor đã được gán. |

`degree_aware` không phải METIS, nhưng đủ để chứng minh partitioning tốt hơn có thể giảm cross-worker communication.

## Edge-cut ratio

Edge-cut ratio được tính bằng:

```text
edge_cut_ratio = cross_worker_edges / total_edges
```

Nếu edge-cut ratio cao, nhiều cạnh đi qua ranh giới giữa các worker. Trong Distributed PageRank, mỗi cross-worker edge sẽ tạo remote rank-score message, vì vậy edge-cut càng cao thì network overhead càng lớn.

## Network overhead model

Mỗi remote rank-score message gồm:

- `4 bytes`: destination page id.
- `8 bytes`: PageRank score.

Mỗi batch trao đổi giữa 2 worker có thêm `32 bytes` header.

```text
network_bytes = remote_messages * 12 + active_worker_pairs * 32
```

Đây là logical network overhead. Nếu triển khai thật bằng TCP/HTTP/gRPC, overhead thực tế sẽ cao hơn.

## Kết quả mẫu

Kết quả SNAP 100k, 4 workers, tolerance `1e-6`:

| Partition strategy | Edge-cut ratio | Worker balance | Iterations | Remote messages | Network MB |
| ------------------ | -------------: | -------------: | ---------: | --------------: | ---------: |
| random             |         0.7498 |         0.9891 |         65 |      15,784,340 |     180.66 |
| hash               |         0.7488 |         0.9926 |         65 |      15,764,580 |     180.44 |
| degree_aware       |         0.0469 |         0.9696 |         65 |         986,310 |      11.31 |

Nhận xét: `degree_aware` giảm edge-cut ratio rất mạnh, nên số remote messages và network overhead cũng giảm nhiều.

## Demo lỗi Node B

Lệnh demo:

```powershell
python failure_demo.py --edge-list data\web-Stanford.txt.gz --nodes 281903 --one-based --limit-nodes 10000 --fail-worker 1 --fail-iteration 3 --max-iterations 6
```

Nếu không có dataset SNAP, vẫn có thể chạy demo synthetic:

```powershell
python failure_demo.py
```

Trong output cần chú ý 3 dòng:

```text
[FAULT] Node B was killed during rank swapping.
[RECOVERY] Coordinator detected missing heartbeat from Node B.
[RECOVERY] Partition 1 reassigned to Node A.
```

Lưu ý: đây là mô phỏng logical site failure, không phải kill process thật.

## Mapping với yêu cầu đồ án

| Yêu cầu                | File tương ứng                                           |
| ---------------------- | -------------------------------------------------------- |
| Project proposal       | `PROJECT_PROPOSAL.md` hoặc bản Word/PDF xuất từ file này |
| 2-page design document | `DESIGN_DOCUMENT_2_PAGE.md` hoặc bản Word/PDF            |
| Code repository        | 3 file `.py` + README này                                |
| Analysis report        | `ANALYSIS_OZSU_VALDURIEZ.md` hoặc bản Word/PDF           |
| Proof video            | Quay màn hình chạy PageRank và failure demo              |

## Ghi chú

- Repository này ưu tiên sạch để nộp GitHub/GitLab.
- File dataset trong `data/` không được commit.
- Các kết quả chi tiết trong `results/experiments/` không được commit.
- Chỉ giữ summary nhỏ: `results/experiment_summary.csv` và `results/experiment_summary.json`.
