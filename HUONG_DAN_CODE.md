# Hướng dẫn mã - GPS Forensics cho sinh viên năm 3

## Luồng demo

1. `main.py` tạo QApplication và Window. Nhập CSV hoặc chạy Batch, xem ảnh/metadata.
2. Mở GPS Forensics Investigation; thay ngưỡng độ, xem bảng nguồn và cảnh báo.
3. Xuất CSV/JSON/HTML; xem Timeline riêng, không gán múi giờ.
4. Dùng các tab JPEG/Batch/ML và PDF như trước. Kết quả GPS mới không khẳng định thật/giả.

## Các hàm GPS quan trọng

- `gps_decimal(dms, ref)` nhận tuple/list ba số độ-phút-giây và N/S/E/W; trả số thập phân hoặc None. Kiểm tra hữu hạn, phút/giây và giới hạn theo trục.
- `normalize_gps(latitude, longitude)` trả dict chứa raw_*, tọa độ hợp lệ nếu có, provided và status. `missing` là thiếu thành phần; `invalid` là có dữ liệu sai. Không ghi vào ảnh hoặc CSV.
- `valid_gps(latitude, longitude)` là phép kiểm tra nhanh status == valid.
- `gps_pair(source)` lấy hai giá trị từ dict latitude/longitude, lat/lon hoặc cặp hai phần tử.
- `gps_sources(record)` trả ba nguồn riêng CSV/EXIF/reference. CSV đọc csv_original, EXIF đọc exif; tọa độ không rõ nguồn không tự trở thành EXIF.
- `compare_gps_sources(csv_gps, exif_gps, tolerance)` trả hai nguồn đã chuẩn hóa, delta vĩ độ/kinh độ tính bằng độ, status và reason. Khi một nguồn thiếu/sai, delta là None và status là insufficient. Ngưỡng 0.0001 độ mặc định có thể thay đổi. Việc so khớp kỹ thuật không chứng minh nguồn đáng tin cậy.
- `analyze_rules(records, gps_tolerance_deg)` duyệt từng ảnh và timestamp, trả dict alerts/comparisons/gps_summary. Không tạo cặp ảnh hay suy đoán quan hệ giữa ảnh. Cảnh báo chứa nguồn và raw evidence; thiếu EXIF được phân biệt với thiếu CSV.

## Nhiệm vụ từng module

- `core/metadata.py`: đọc CSV, kiểm tra filename, đọc EXIF/IFD và GPS. Giữ csv_original, exif, gps_raw và gps_parse_invalid. DMS sai còn bằng chứng thay vì bị biến thành chỉ thiếu GPS.
- `core/map_view.py`: thêm marker nguồn hợp lệ vào lớp CSV/EXIF/reference; LayerControl cho phép tách hai nguồn trùng vị trí. Folium tự sinh HTML; không viết JavaScript và không vẽ tuyến.
- `core/timeline.py`: đọc ISO/EXIF, phân biệt giờ có offset/không offset, sắp xếp/lọc và nhận diện thời gian trùng. Không gán múi giờ.
- `core/reporting.py`: chỉ nhận cấu hình gps_tolerance_deg, gọi luật mới, giữ thống kê nguồn GPS và danh sách đối chiếu. Snapshot JSON/PDF không có cấu hình phân tích GPS cũ. PDF dùng font Unicode và bảng minh chứng cảnh báo theo file.
- `gui/main_window.py`: tái sử dụng cửa sổ chính. Hộp thoại GPS có danh sách ảnh, bảng EXIF/CSV, cảnh báo, bản đồ, ngưỡng độ và nút xuất. Chọn dòng GPS đồng bộ ảnh ở cửa sổ chính.
- `gui/stage4_tabs.py`: cấu hình báo cáo lấy từ gps_tolerance_deg; giữ ML ảnh, histogram, snapshot, PDF nền và xử lý lỗi bản đồ. Không còn thuộc tính giao diện GPS cũ.
- `core/batch.py`, `core/integrity.py`, `core/jpeg_analysis.py`, `gui/forensics_tabs.py`: tiếp tục xử lý tuần tự trên QThread, hash, JPEG/MAE/histogram và so ảnh; chỉ đọc file gốc.
- `core/stage4_analysis.py`, `core/machine_learning.py`: tính đặc trưng ảnh và Isolation Forest; không đưa GPS/timestamp vào mô hình.
- `core/experiments.py`: bản sao dữ liệu can thiệp, dùng alerts trong kết quả luật mới. Thông tin thiếu một nguồn khi nguồn khác hợp lệ không được coi là lỗi can thiệp.
- `core/legacy.py`: giữ tương thích các chức năng cũ; phần GPS và bản đồ gọi module dùng chung, tránh có hai cách giải mã nguồn GPS.

## Kiểm thử

Chạy tại D:\GeoImageForensics:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

- test_gps: tọa độ/DMS, NaN/Inf/thiếu, chuẩn hóa, các mức ngưỡng và raw EXIF sai trên ảnh tạm.
- test_anomaly: cảnh báo theo nguồn, timestamp, không thay đầu vào, thiếu nguồn thì insufficient.
- test_map: marker riêng hai nguồn, dữ liệu sai, nội dung popup an toàn, không có tuyến và dataset 100 ảnh.
- test_gui_stage2: bảng mới, thay ngưỡng, chọn/xem ảnh, CSV/JSON/HTML và trường hợp thiếu QtWebEngine; kiểm tra thuộc tính cũ không tồn tại.
- test_reporting: PDF/JSON Unicode, thống kê GPS, cấu hình mới và từ chối cấu hình không hỗ trợ.
- Các bài metadata, ML, Batch, SHA-256, JPEG, Timeline và GUI khác tiếp tục là hồi quy; không sửa dataset để đạt kiểm thử.

## Giới hạn cần nói rõ khi bảo vệ

100 ảnh chỉ có GPS CSV nên không đối chiếu được GPS EXIF/CSV; thiếu nguồn không phải khác biệt và cũng không phải khớp. Tọa độ hợp lệ có thể đã bị sửa mà không có nguồn đáng tin cậy để phát hiện. EXIF và CSV đều có thể bị sửa. Không dùng MAE, hash, GPS hoặc Anomaly như nhãn thật/giả. Ngưỡng độ là lựa chọn kỹ thuật của demo, không phải chuẩn pháp chứng bắt buộc.
