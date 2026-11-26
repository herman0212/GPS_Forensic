# Hướng dẫn mã nguồn GeoImageForensics

## 1. Khởi chạy và luồng dữ liệu

Chạy PowerShell tại thư mục dự án, ví dụ `D:\GeoImageForensics`:

```powershell
.\.venv\Scripts\python.exe main.py
```

`main.py` tạo `QApplication` và `gui.main_window.Window`. Cửa sổ này kế thừa giao diện nền từ `core/legacy.py`, rồi tổ chức tám tab: Danh sách ảnh và Metadata, Batch Processing, JPEG Analysis, Tổng quan, GPS Map, Timeline, Anomaly Detection và Báo cáo. Tab Tổng quan được chọn khi khởi chạy.

```text
Nhập CSV → load_dataset() → bản ghi có csv_original và exif
Chọn thư mục → Batch QThread → bản ghi đọc từ ảnh/EXIF
                                     ↓
                    Đưa kết quả sang Metadata / Timeline
                                     ↓
                       Thay danh sách bản ghi hiện tại
```

Batch không tự ghép CSV. Muốn đối chiếu EXIF/CSV, nhập CSV trực tiếp; sau khi chuyển Batch sang Metadata, cần nhập lại CSV. Việc thay danh sách trong bộ nhớ không xóa dữ liệu nguồn.

## 2. Metadata và EXIF

Module chính: `core/metadata.py`; hiển thị: `gui/main_window.py`.

| Hàm | Đầu vào | Xử lý và đầu ra |
|---|---|---|
| `read_exif(path)` | Đường dẫn ảnh | Pillow đọc ảnh, IFD EXIF và GPS; trả dict gồm timestamp, offset, tọa độ, thiết bị, thẻ và dữ liệu GPS gốc |
| `load_dataset(csv_path)` | CSV cạnh thư mục `images/` | Kiểm tra cột, ghép `filename`, đọc EXIF và trả list bản ghi |
| `export_rows(rows, path)` | List dict và đường dẫn đầu ra | Xuất CSV UTF-8 BOM; dict/list lồng nhau được ghi thành chuỗi JSON |

Tám cột bắt buộc là `filename`, `lat`, `lon`, `gps_altitude`, `timestamp`, `timestamp_raw`, `camera_make`, `camera_model`. CSV demo có thêm `img_id`, `split`, nhưng hàm nhập không bắt buộc hai cột này. Tên ảnh phải nằm trực tiếp trong `images/`, không có dấu phân cách đường dẫn. Thiếu cột bắt buộc làm dừng nhập; lỗi đọc từng ảnh được lưu thành cảnh báo.

`csv_original` giữ dòng CSV ban đầu; `exif` chứa thông tin đọc từ ảnh. Các trường cấp ngoài phục vụ hiển thị không thay thế hai phần nguồn. Khi nhập CSV, timestamp/GPS hiển thị lấy từ CSV; GPS CSV sai có thể được đặt thành `None` ở cấp ngoài nhưng vẫn còn trong `csv_original`. `timestamp_raw` là dự phòng khi `timestamp` rỗng; EXIF không tự thay timestamp CSV sai.

`read_exif()` đọc `getexif()`, IFD EXIF `0x8769` và GPS `0x8825`. `gps_raw` giữ thông tin GPS; `gps_parse_invalid` đánh dấu thành phần DMS được cung cấp nhưng không giải mã hợp lệ. Luồng phân tích hiện tại dùng Pillow. Hàm hỗ trợ ExifTool còn trong `legacy.py` nhưng không được `read_exif()` hoặc Batch tự gọi.

## 3. GPS, Timeline và bản đồ

### Các hàm GPS trong core/gps.py

| Hàm | Ý nghĩa |
|---|---|
| `gps_decimal(dms, ref)` | Nhận tuple/list ba thành phần DMS và hướng N/S/E/W; trả độ thập phân có dấu hoặc `None` khi thiếu/sai |
| `normalize_gps(latitude, longitude)` | Trả dict có `status`, `provided`, `raw_*` và cặp tọa độ chuẩn hóa khi hợp lệ |
| `valid_gps(latitude, longitude)` | Kiểm tra nhanh trạng thái `valid` |
| `validate_tolerance(tolerance)` | Chỉ nhận ngưỡng hữu hạn, không âm, đơn vị độ tọa độ |
| `gps_pair(source)` | Lấy tọa độ từ dict `raw_*`, `latitude/longitude`, `lat/lon` hoặc cặp hai phần tử |
| `gps_sources(record)` | Tách CSV, EXIF và reference; không đổi nhãn tọa độ chưa rõ nguồn thành EXIF |
| `compare_gps_sources(csv_gps, exif_gps, tolerance=0.0001)` | Đối chiếu khi hai nguồn hợp lệ; trả nguồn chuẩn hóa, độ lệch, trạng thái và lý do |

GPS hợp lệ cần vĩ độ trong [-90, 90], kinh độ trong [-180, 180] và số hữu hạn. Boolean không được coi là tọa độ. DMS cần phút/giây từ 0 đến dưới 60, độ không âm và kết quả không vượt giới hạn theo hướng. `read_exif()` kiểm tra riêng hướng vĩ độ N/S và kinh độ E/W.

`missing` nghĩa là thiếu thành phần và không có thành phần sai; nếu vừa thiếu vừa có giá trị sai thì trạng thái là `invalid`. `provided` chỉ cho biết ít nhất một thành phần được cung cấp, không xác nhận đủ hoặc hợp lệ. Không tự kẹp phạm vi hay ghi giá trị trở lại nguồn.

```text
Hai nguồn hợp lệ?
├── Không → insufficient; không có độ lệch để kết luận khớp/khác
└── Có → tính abs(lat_csv - lat_exif), abs(lon_csv - lon_exif)
         ├── Cả hai trong ngưỡng → match
         └── Ít nhất một vượt ngưỡng → difference
```

Ngưỡng mặc định 0.0001 độ có thể đổi, kể cả đặt 0 để so chính xác. Mã dùng `isclose` rất nhỏ tại biên ngưỡng dương để giảm ảnh hưởng sai số float. Không tính khoảng cách, vận tốc hoặc hành trình. Reference được hỗ trợ trong dữ liệu/bản đồ nhưng không thay EXIF/CSV trong đối chiếu hai nguồn; giao diện chưa có luồng nhập tham chiếu chuyên biệt.

### Quy tắc và Timeline

`core/anomaly.py: analyze_rules(records, gps_tolerance_deg=0.0001)` trả `alerts`, `comparisons`, `gps_summary`. Cảnh báo có `file`, `kind`, `description`, `value`, `level`, `source`. Các mã gồm `gps_missing`, `gps_invalid`, `gps_source_difference`, `time_missing`, `time_invalid`, `time_duplicate`, `timezone_unknown`, `timezone_difference`.

Thiếu một nguồn khi nguồn khác hợp lệ được ghi mức Thông tin; vẫn chưa đủ đối chiếu. `valid` đếm ảnh có ít nhất một nguồn hợp lệ, `invalid` đếm ảnh có ít nhất một nguồn sai, nên hai nhóm có thể giao nhau. `different=0` cùng `comparable=0` không có nghĩa hai nguồn khớp. Cảnh báo thời gian dựa trên timestamp của bản ghi đang hoạt động; kiểm tra timezone còn xem timestamp CSV/EXIF khi đọc được.

`core/timeline.py` có `parse_time()` đọc ISO 8601 hoặc EXIF `%Y:%m:%d %H:%M:%S`; `time_key()` quy đổi timestamp có offset về UTC để so sánh, giữ timestamp không offset trong nhóm riêng. `build_timeline()` trả danh sách sắp xếp, trạng thái trùng và chênh lệch giây trong cùng nhóm. Hai mốc lọc phải cùng loại thông tin múi giờ và tăng dần; thời gian thiếu/sai bị loại khi áp dụng lọc thời gian. Không tự gán UTC hoặc UTC+07:00 cho ảnh.

### GPS Map

`core/map_view.py` tạo lớp CSV xanh dương, EXIF xanh lá và reference xám. Mỗi nguồn hợp lệ có marker và popup ghi nguồn; hai nguồn trùng vị trí vẫn có marker riêng. `LayerControl` cho bật/tắt lớp. Nội dung popup được escape HTML; không có tuyến tự động.

Folium tự sinh HTML/JavaScript, không có JavaScript tự viết. QtWebEngine hiển thị HTML; thư viện trên mạng và bản đồ nền cần Internet. Thiếu QtWebEngine vẫn có thể xuất HTML. Tín hiệu HTML tải thành công không tự chứng minh mọi tài nguyên nền đã tải đủ.

## 4. Batch Processing và SHA-256

`core/batch.py` chứa logic độc lập Qt. `gui/forensics_tabs.py: AnalysisWorker` dùng QThread để gọi logic và phát tín hiệu. `run_batch()` xử lý tuần tự, không chạy nhiều ảnh song song. Lỗi từng tập tin được ghi nhận; hủy có hiệu lực giữa hai ảnh. Đóng cửa sổ trong lúc worker chạy yêu cầu kết thúc/hủy an toàn, không cưỡng bức hủy QThread.

| Hàm | Công việc |
|---|---|
| `list_images(folder, recursive=False)` | Quét `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp`; tùy chọn thư mục con |
| `analyze_file(path, quality=90)` | Hash trước, đọc ảnh/EXIF, phân tích JPEG khi phù hợp; luôn cố tính hash sau; trả dict thành công/lỗi |
| `run_batch(paths, quality=90, cancelled=None, progress=None)` | Trả rows, số xử lý/thành công/thất bại, trạng thái hủy và thời gian |
| `recheck_hashes(rows, cancelled=None)` | Đối chiếu hiện trạng với hash ban đầu, không thay mốc |

Phần mở rộng quyết định lựa chọn khi quét; Pillow xác định định dạng thực tế. JPEG còn được nhận diện bằng chữ ký để kiểm tra cấu trúc kể cả khi giải mã lỗi. PNG/TIFF/WebP không có MAE tái nén JPEG; EXIF chỉ có khi tồn tại và đọc được.

`core/integrity.py: sha256_file(path)` đọc theo khối 1 MiB để tính SHA-256 toàn tập tin. `annotate_duplicates()` phân biệt trùng hash và trùng tên không phân biệt hoa/thường. Hash trống không được dùng suy ra trùng nội dung. Hash trước/sau trùng chỉ xác minh byte trong khoảng đo. `hash_unchanged=False` cần đọc kèm lỗi và mốc; không mặc nhiên kết luận file bị sửa nếu thiếu hash hoặc đọc lỗi. SHA-256 là hàm băm, không phải mã hóa.

## 5. JPEG Analysis và so sánh ảnh

Module chính: `core/jpeg_analysis.py`; hiển thị: `gui/forensics_tabs.py`.

- `image_information(path)`: đọc định dạng thực tế, kích thước, mode, số byte và thông tin kỹ thuật JPEG khi có.
- `inspect_jpeg_structure(path)`: kiểm tra SOI/EOI, độ dài segment, SOF/SOS và theo dõi DQT/DHT; xử lý byte stuffing, restart và nhiều scan. `structure_ok` là kiểm tra cơ bản, không thay xác minh toàn bộ chuẩn hoặc giải mã. DQT/DHT thiếu được báo riêng vì không phải mọi kiểu JPEG đều dùng chúng. Pillow kiểm tra giải mã trong pipeline.
- `recompress_jpeg(path, quality=90)`: chỉ nhận JPEG thực tế; chuyển RGB, tái nén trong BytesIO, giải mã lại và trả MAE, ảnh sai khác, histogram. Quality từ 1 đến 100 là tham số mã hóa, không phải phần trăm thông tin giữ lại.
- `pixel_mae(first, second)`: yêu cầu cùng shape, không rỗng; chuyển kiểu số trước phép trừ để tránh tràn uint8; trả trung bình sai khác tuyệt đối.
- `compare_images(first_path, second_path)`: so thông tin và hash khi đọc được ảnh; chỉ tính MAE RGB nếu cùng kích thước, không resize. Hash trùng và pixel giống là hai phép kiểm tra khác nhau.

MAE = tổng sai khác tuyệt đối của các thành phần RGB / (3 × chiều rộng × chiều cao). Histogram đếm thành phần RGB tại mỗi mức sai khác 0–255. `difference` là ảnh sai khác gốc; `difference_display` được tăng tương phản để quan sát. Không dùng độ sáng ảnh hiển thị thay giá trị sai khác gốc.

MAE cao hoặc dữ liệu sau EOI chỉ là thông tin cần xem xét. Chưa có ngưỡng MAE phân loại thật/giả hoặc chức năng định vị vùng giả mạo được xác minh bằng ground truth.

## 6. Machine Learning

`core/machine_learning.py` dùng `file_bytes`, `width`, `height`, `jpeg_recompress_mae`. Không dùng GPS, timestamp, filename hoặc nhãn làm đầu vào. Đây là ngoại lệ kỹ thuật ảnh, chưa phải mô hình phát hiện thay đổi GPS.

`prepare_features()` giữ chỉ số dòng để ghép kết quả. Bản ghi `success=False` hoặc thiếu toàn bộ đặc trưng nhận Excluded. Cột thiếu toàn bộ bị bỏ; ô thiếu còn lại điền trung vị học từ tập huấn luyện. Dung lượng/kích thước 0 không hợp lệ, MAE 0 vẫn hợp lệ. Cần ít nhất năm dòng phù hợp và dữ liệu có biến thiên để huấn luyện.

`train_model()` dùng IsolationForest với 100 cây, contamination mặc định 0.1, random_state 42, n_jobs 1. Contamination phải lớn hơn 0 và không quá 0.5. `predict_model()` dùng lại trung vị đã học, trả Normal/Anomaly/Excluded, `anomaly_score`, `decision_function`. Điểm hiển thị là `-score_samples`, lớn hơn nghĩa là khác biệt hơn; `decision_function < 0` gắn nhãn Anomaly. Điểm không phải xác suất giả mạo.

`run_isolation_forest()` học và dự đoán cùng tập để phân tích thăm dò, không phải đánh giá trên tập độc lập. Không suy ra tỷ lệ giả mạo từ contamination hoặc số Anomaly. `evaluate_labels()` chỉ có ý nghĩa khi nhãn phù hợp mục tiêu đánh giá.

`core/stage4_analysis.py: collect_features()` tạo bản sao, tái sử dụng đặc trưng hoặc phân tích ảnh để bổ sung. Chỉ ghép các trường phân tích ảnh, không ghi đè GPS/timestamp CSV. MAE có thể được dùng lại từ Batch theo quality đã lưu; không mặc định mỗi lần chạy ML đều tái nén lại ở quality 90.

`dataset_signature()` là hash trạng thái bản ghi trong RAM để tránh dùng kết quả ML khi bộ bản ghi đổi. Nó không kiểm tra lại tập tin trên đĩa và không thay `sha256_file()`. `gui/stage4_tabs.py` chạy thu thập đặc trưng, ML và PDF trên worker với snapshot; bỏ ML trả về nếu trạng thái bản ghi không khớp. Hủy không ngắt cưỡng bức giữa một lệnh fit hoặc xuất PDF.

`core/experiments.py: controlled_experiment()` can thiệp bản sao metadata/đặc trưng, không sửa JPEG nguồn. Nhãn mô tả can thiệp tổng hợp, không phải nhãn ảnh giả mạo. Không dùng chỉ số đó như độ chính xác xác thực ảnh trên tập gốc.

## 7. Báo cáo và xuất kết quả

`core/reporting.py: build_report()` tạo bản sao, chỉ nhận cấu hình luật `gps_tolerance_deg`, tổng hợp metadata, GPS, Timeline, hash, JPEG, cảnh báo và ML khi được cung cấp. ML phải khớp số lượng, tên, đường dẫn bản ghi. Hash/JPEG chưa đo ghi là chưa phân tích; không tự tạo số liệu. Thời điểm lập báo cáo UTC+07:00 không phải timezone suy đoán cho ảnh.

`gui/stage4_tabs.py: snapshot()` dùng bản ghi bổ sung đặc trưng nếu có, nên PDF/JSON ở tab Báo cáo có thể đầy đủ hơn CSV/JSON metadata trên thanh công cụ. JSON điều tra GPS cũng là đầu ra riêng. Chọn đúng chức năng xuất theo mục đích.

`export_pdf()` dùng ReportLab và font Arial hoặc DejaVu có sẵn để hiển thị tiếng Việt. PDF có thống kê, biểu đồ, cảnh báo theo file, ML khi có và giới hạn. Chưa chạy ML thì không tự tạo nhãn.

`protect_output()` chặn `data/`, vùng `outputs/chapter3_evidence`, tên bắt đầu `stage3_` và đường dẫn trùng file nguồn được ghi trong bản ghi. Không suy rộng rằng mọi hàm xuất đều có cùng bảo vệ: `export_rows()` và `export_map()` là hàm ghi file thông thường; một số thao tác GUI không gọi `protect_output()`. Luôn chọn đầu ra riêng, tránh ghi đè dữ liệu và minh chứng cũ.

## 8. Dữ liệu và kiểm chứng

Tập 100 JPEG Image2GPS-25 cục bộ không có EXIF gốc; GPS từ CSV, timestamp không offset. Bộ này không đủ đối chiếu EXIF/CSV. Tám JPEG có kiểm soát ở `outputs/gps_forensics/demo_evidence/experiments/` có GPS EXIF thật theo từng tình huống và CSV riêng; dùng khi demo khớp, lệch, thiếu nguồn, ngoài phạm vi và timestamp sai.

Ảnh/CSV Image2GPS-25 và `outputs/` bị `.gitignore` loại khỏi Git; clone không tự có dữ liệu. `download_dataset.py` là tiện ích chuẩn bị dữ liệu dùng thêm `datasets`, chưa nằm trong requirements ứng dụng. Không chạy lại để ghi lên bộ ảnh đã có.

Chạy bộ kiểm thử hiện có:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

| Nhóm kiểm thử | Nội dung chính |
|---|---|
| `test_stage1.py` | Metadata, CSV, Timeline, bảo toàn ảnh tạm và đọc dataset 100 ảnh |
| `test_gps.py`; `test_anomaly.py` | DMS, NaN/Inf, thiếu/sai, ngưỡng, nguồn và timestamp |
| `test_map.py`; `test_gui_stage2.py` | Marker, popup, không vẽ tuyến, GUI GPS, xuất file và thiếu QtWebEngine |
| `test_batch.py`; `test_gui_stage3.py` | Batch, hash, lỗi, hủy, JPEG và so sánh trong GUI |
| `test_jpeg_analysis.py` | Cấu trúc, tái nén, histogram, MAE và định dạng thực tế |
| `test_machine_learning.py` | Đặc trưng, dữ liệu thiếu, cấu hình, nhãn, điểm và can thiệp tổng hợp |
| `test_reporting.py`; `test_gui_stage4.py` | PDF/JSON, Unicode, bảo vệ đầu ra, worker và bỏ kết quả lỗi thời |

Kiểm thử Batch có JPEG, PNG và TIFF tạm; chưa có bài riêng cho WebP. Không suy ra đã kiểm chứng EXIF mọi định dạng. Một số bài đọc dataset thật nên cần chuẩn bị dữ liệu. Kiểm thử GUI dùng Qt offscreen và thay một số thao tác chọn file/tải bản đồ; không xác minh đầy đủ desktop và Internet. Số bài kiểm thử không phải phần trăm bao phủ mã nguồn khi chưa đo coverage.

Các script thực nghiệm trong `tests/` dùng đầu ra cố định; đọc trước khi chạy để tránh ghi đè kết quả. Log đã lưu phản ánh lần chạy và phiên bản tương ứng, không phải phép kiểm tra mới của lần đọc tài liệu này.

## 9. Giới hạn cần nêu khi bảo vệ

- CSV và EXIF lưu riêng nhưng không mặc định độc lập hoặc đáng tin cậy. Khớp không chứng minh vị trí chụp.
- GPS thiếu nguồn dẫn đến chưa đủ dữ liệu; tọa độ hợp lệ vẫn có thể sai thực tế hoặc đã bị sửa.
- Timestamp thiếu offset không tự được gán múi giờ; thời gian gần nhau không chứng minh cùng hành trình.
- Hash kiểm tra byte giữa các lần đo, không chứng minh ảnh chưa từng sửa hoặc nguồn gốc chụp.
- MAE, marker JPEG và Anomaly cung cấp dấu hiệu, không phải kết luận thật/giả.
- Thực nghiệm JPEG chính và dữ liệu tổng hợp có phạm vi riêng, không suy rộng sang mọi định dạng hoặc giả mạo thực tế.
- Không sửa ảnh/CSV gốc để tạo kết quả mong muốn; lưu đầu ra riêng và phân biệt hash ảnh nguồn với hash minh chứng.
