# GeoImageForensics

Đồ án nghiên cứu Image Forensics bằng Python cho sinh viên năm 3 ngành An toàn thông tin. Ứng dụng desktop PySide6 hỗ trợ đọc thông tin ảnh và kiểm tra dữ liệu, không kết luận ảnh giả mạo từ GPS, timestamp hay JPEG MAE.

## Phạm vi hiện tại: Giai đoạn 1–4

- Nhập Dataset CSV, ghép filename với thư mục images/ nằm cạnh CSV.
- Giữ nguyên từng dòng CSV trong csv_original; EXIF đọc trực tiếp nằm trong exif.
- Hiển thị GPS, camera, altitude trong chi tiết và ảnh xem trước khi chọn dòng.
- Báo thiếu ảnh, filename không hợp lệ, GPS/timestamp/altitude thiếu hoặc sai.
- Timeline sắp xếp riêng giờ có offset và giờ chưa rõ múi giờ; phát hiện thiếu, sai, trùng timestamp, tính chênh lệch giây, lọc và xuất CSV.
- Giữ các nút chọn thư mục, xuất CSV/JSON, bản đồ và ML thử nghiệm cũ. Không tự nối hành trình hoặc tính tốc độ giữa các ảnh.

Đã kiểm tra dữ liệu ban đầu: 100 dòng, 100 ảnh JPEG đọc được, không thiếu ảnh; 100 ảnh không có EXIF. Tất cả trường CSV có giá trị, timestamp không có timezone. CSV này là metadata dataset, không phải EXIF nhúng trong JPEG đã chuyển đổi.

## Cấu trúc

- main.py: điểm khởi chạy.
- core/metadata.py: nhập CSV, đọc EXIF và xuất bảng.
- core/gps.py: kiểm tra tọa độ hữu hạn và giới hạn.
- core/timeline.py: phân tích thời gian và lọc Timeline.
- core/legacy.py: chức năng thử nghiệm từ chương trình cũ.
- gui/main_window.py: mở rộng giao diện cũ cho Giai đoạn 1.
- tests/test_stage1.py: kiểm thử pytest.
- data/Image2GPS25/: dữ liệu gốc, chỉ đọc khi phân tích.
- outputs/: nơi gợi ý lưu báo cáo.

## Cài đặt và chạy trong PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Chọn **Nhập Dataset CSV**, mở data/Image2GPS25/metadata.csv. Chọn một dòng để xem ảnh và nguồn metadata. Nhập mốc ISO 8601 ở hai ô lọc, để trống để bỏ giới hạn. Mốc không có offset chỉ lọc nhóm chưa rõ múi giờ; mốc có offset chỉ lọc nhóm có múi giờ. Chênh lệch Timeline là khoảng thời gian giữa hai bản ghi trong nhóm đang hiển thị, không chứng minh cùng hành trình.

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

Bộ kiểm thử gồm dữ liệu nhỏ trước và bài tích hợp 100 ảnh sau. Môi trường kiểm thử: Python 3.14.3 và pytest 9.2.0.

## Thuật toán và các giai đoạn tiếp theo

Timeline đọc ISO 8601 hoặc định dạng EXIF YYYY:MM:DD HH:MM:SS. Thời gian có offset được chuẩn hóa UTC khi so sánh; thời gian không offset được giữ nguyên. Timestamp tương đương ở các offset khác nhau được nhận diện trùng. Không tự gán UTC hay giờ Việt Nam.

Haversine đã được bổ sung trong Giai đoạn 2, xem giải thích và hướng dẫn bên dưới.

JPEG MAE: chuyển RGB, tái nén trong bộ nhớ (mặc định quality=90), tính trung bình trị tuyệt đối sai khác trên mọi thành phần pixel. Giai đoạn 3 thêm cấu trúc JPEG, ảnh sai khác và histogram; xem hướng dẫn dưới. MAE không chứng minh ảnh bị sửa.

Isolation Forest cũ dùng GPS và thời gian, chuẩn hóa đặc trưng, contamination=0.1; nhãn -1 là điểm ngoại lệ trong tập đang xét. Không phải nhãn giả mạo hay xác suất giả mạo. Cấu hình contamination, anomaly score và so sánh luật đã được bổ sung ở Giai đoạn 4; nút ML hiện chuyển tới mô hình đặc trưng ảnh.

## Giới hạn

Giai đoạn 4 đã thêm tám tab chức năng, PDF Unicode và Isolation Forest; xem hướng dẫn bên dưới. Batch, kiểm tra lại hash, phân tích JPEG và so sánh hai ảnh chạy trên QThread; nhập CSV vẫn đồng bộ. Bản đồ Folium mở HTML và cần Internet cho bản đồ nền. Không sửa metadata hoặc ảnh gốc. Khi tải lại dataset bằng download_dataset.py, script tải cũ có thể ghi đè dữ liệu; không cần chạy để sử dụng 100 ảnh hiện có.


## Giai đoạn 2: GPS, vận tốc, cảnh báo và bản đồ nhúng

1. Nhập CSV hoặc thư mục như trước, bấm **GPS / Khoảng cách / Bản đồ / Cảnh báo**.
2. Trong tab **Ảnh / Nhóm xác nhận**, giữ Ctrl/Shift chọn ảnh, nhập tên nhóm, bấm **Gán nhóm cho ảnh chọn** khi đã có căn cứ cùng hành trình. Có nút bỏ nhóm. Đây là ghi chú trong bộ nhớ, không sửa CSV/EXIF gốc.
3. **So sánh 2 ảnh chọn** tính khoảng cách giữa hai GPS hợp lệ. Vận tốc cần cùng nhóm và timestamp so sánh được. Với giờ không offset, cần đánh dấu xác nhận dùng cùng cơ sở đồng hồ. Không tự gán múi giờ và không so giờ có offset với giờ không offset.
4. Chỉnh ngưỡng khoảng cách (mặc định 500 km), vận tốc (900 km/h), sai khác CSV/EXIF (0,1 km), rồi bấm **Phân tích lại / cập nhật bản đồ**. Bấm lại sau khi đổi xác nhận đồng hồ.
5. Các tab hiển thị cặp liên tiếp theo thời gian trong từng nhóm và loại múi giờ; cảnh báo có tên ảnh, loại, mô tả, giá trị và mức. Timestamp trùng toàn tập không chứng minh cùng hành trình.
6. **GPS Map** nhúng QWebEngineView, marker có tên ảnh, timestamp, GPS và nguồn. Nút xuất HTML dùng cùng hàm tạo bản đồ. Không nối đường tự động. Internet cần cho Leaflet và bản đồ nền; HTML đã nạp không bảo đảm mạng đã tải đủ bản đồ nền. Nếu thiếu QtWebEngineWidgets, giao diện thông báo và vẫn cho xuất HTML.

### Thuật toán

Haversine đổi tọa độ sang radian, tính `a = sin²(Δlat/2) + cos(lat1) cos(lat2) sin²(Δlon/2)`, giới hạn a trong [0,1] để tránh sai số rồi tính `d = 6371 × 2 × atan2(√a, √(1-a))` km. Đây là khoảng cách đường chim bay trên mô hình Trái Đất hình cầu, không phải đường bộ.

Vận tốc trung bình = khoảng cách km / (số giây / 3600). Không chia khi thời gian bằng 0 hoặc âm. Giờ có offset khác nhau được so sánh theo cùng thời điểm UTC. Với giờ không offset, xác nhận đồng hồ là giả thiết do người dùng cung cấp, không phải dữ liệu EXIF hay timezone tự suy đoán.

Luật gồm GPS thiếu/sai, timestamp thiếu/sai/trùng, chưa rõ/khác thông tin múi giờ, thời gian 0, khoảng cách và vận tốc vượt ngưỡng trong nhóm xác nhận, GPS EXIF lệch CSV vượt ngưỡng. Không kết luận giả mạo.

Tập 100 ảnh hiện tại chưa có nhóm xác nhận và không có timezone: mặc định không tính vận tốc. Không chọn xác nhận đồng hồ chỉ để tạo ra kết quả. Nhóm không tự khôi phục giữa các phiên; xuất CSV/JSON ảnh có lưu trường journey_group như ghi chú người dùng.

### File mới và kiểm thử

- core/gps.py: Haversine và điều kiện so sánh vận tốc.
- core/anomaly.py: luật cảnh báo, nhóm xác nhận, các cặp liên tiếp.
- core/map_view.py: Folium marker và xuất HTML dùng chung với giao diện.
- gui/main_window.py: cửa sổ Giai đoạn 2; giữ giao diện và chức năng Giai đoạn 1.
- tests/test_gps.py, test_anomaly.py, test_map.py, test_gui_stage2.py: các ca tính toán, điều kiện, nguồn dữ liệu, 100 marker và tích hợp GUI offscreen. Các bài bản đồ kiểm thử không tải mạng.

Chạy toàn bộ: `.\.venv\Scripts\python.exe -m pytest -v`.


## Giai đoạn 3: Batch Processing, SHA-256 và JPEG Analysis

Không cần cài thêm thư viện; dùng PySide6, Pillow và NumPy đã có trong requirements.txt. Không xóa hoặc tạo lại .venv. Phần này mô tả Giai đoạn 3; phần Giai đoạn 4 bên dưới bổ sung ML và PDF.

### Batch Processing

- Mở tab **Batch Processing**, chọn thư mục, tùy chọn **Quét thư mục con**, chọn chất lượng JPEG rồi bấm **Bắt đầu Batch**. Nút chọn thư mục cũ cũng chuyển sang tab này.
- Hỗ trợ JPG/JPEG, PNG, TIF/TIFF, giữ thêm WebP từ phiên bản trước. Định dạng thực tế do Pillow nhận diện, không suy ra từ tên file.
- Một QThread xử lý tuần tự, signal gửi tiến trình về GUI. Bảng có tổng ảnh, số hoàn tất/thành công/lỗi và thời gian. Một ảnh lỗi không dừng ảnh khác; ảnh không có EXIF vẫn là xử lý thành công nếu đọc được.
- **Hủy an toàn** yêu cầu dừng giữa hai file; ảnh đang đọc được xử lý xong. Không dùng terminate. Nếu đóng khi đang xử lý, cửa sổ yêu cầu hủy và giữ mở; đóng lại sau khi tác vụ kết thúc. Quét danh sách thư mục vẫn hoàn tất trước khi nhận hủy.
- **Xuất kết quả Batch CSV** gồm metadata trích xuất, cấu trúc JPEG, MAE, lỗi và hash. **Đưa kết quả sang Metadata / Timeline** là thao tác chủ động thay bộ ảnh đang xem; trước khi bấm, metadata CSV và GPS/Timeline đang xem được giữ nguyên.

### SHA-256

Từng file được đọc theo khối 1 MiB, tính hash trước và sau phân tích. Bảng hiển thị đầy đủ hai hash và kết quả đối chiếu. **Kiểm tra lại SHA-256** đối chiếu hiện trạng với hash ban đầu, không thay baseline. Có nút xuất riêng bảng hash CSV.

Cột **Cùng byte ban đầu** đếm file có cùng hash lúc bắt đầu; cột **Số file cùng tên** đếm tên file, không xét đường dẫn và không phân biệt hoa/thường như cách dùng thông thường trên Windows. File trùng tên ở thư mục con có thể khác nội dung; file khác tên có thể trùng byte. Hash rỗng không bị gộp thành nhóm trùng. Việc kiểm tra lại hash không đổi nhóm trùng của baseline.

SHA-256 trùng cho thấy nội dung byte giống nhau với độ tin cậy mật mã rất cao, không chứng minh nguồn gốc chụp. Hash trước/sau giống nhau chứng minh trạng thái tại hai lần đo phù hợp; không phải cơ chế khóa file chống thay đổi bởi chương trình bên ngoài.

### JPEG Analysis

- **Chọn ảnh để phân tích JPEG**: xem định dạng thật, kích thước, chế độ màu, dung lượng, thông tin quantization/component sampling/progressive, hash, cấu trúc marker và MAE.
- Parser bắt đầu SOI, đọc mỗi segment theo độ dài big endian (độ dài gồm hai byte trường length). Sau SOS, đọc vùng entropy, bỏ FF00 (byte stuffing), nhận FFD0–FFD7 (restart), xử lý marker tiếp theo và nhiều scan của progressive JPEG.
- Báo SOI/EOI/DQT/DHT/SOF/SOS thiếu, độ dài lỗi, file bị cắt, số byte sau EOI. DQT/DHT có thể vắng trong một số kiểu JPEG nên được báo riêng, không mặc định là giả mạo. Kiểm tra cấu trúc và khả năng Pillow giải mã là hai kiểm tra bổ sung nhau; đây không phải bộ xác minh toàn bộ chuẩn JPEG.
- MAE = tổng `abs(pixel_gốc - pixel_tái_nén)` / tổng số thành phần pixel RGB. Chuyển kiểu số trước phép trừ để không tràn uint8. Mặc định quality=90, chọn 1–100; chỉ tái nén JPEG thực tế và hoàn toàn trong RAM.
- Ảnh sai khác được kéo giãn tương phản để dễ nhìn; MAE và histogram 256 mức vẫn dùng sai khác thật. Histogram đếm tất cả thành phần RGB, không phải chỉ số pixel. Không ghi ảnh tái nén hoặc sai khác đè lên ảnh gốc.
- **Chọn hai ảnh để so sánh**: chọn đúng hai file, xem cạnh nhau cùng định dạng, kích thước, SHA-256, same_bytes và pixel_mae. Hash so byte, MAE so pixel RGB sau giải mã. Không tự resize; khác kích thước thì không tính MAE. Hai file khác byte vẫn có thể có MAE=0.

### Kiểm thử và chạy 100 ảnh

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m tests.benchmark_stage3
```

Benchmark đo thời gian pipeline 100 ảnh quality=90, đối chiếu hash trước/sau của cả ảnh và metadata.csv, xuất outputs/stage3_batch_100.csv, stage3_sha256_100.csv và stage3_validation.json. Thời gian bao gồm hash, giải mã, metadata, parser, tái nén và MAE; không gồm dựng bảng GUI và ghi báo cáo sau pipeline.

### Giới hạn Giai đoạn 3

Parser JPEG hiện nạp file vào RAM; giải mã và MAE cũng cần bộ nhớ theo kích thước ảnh. SHA-256 riêng vẫn đọc theo khối. Batch hủy ở ranh giới file, chưa dừng tức thì giữa một phép giải mã lớn. TIFF chỉ phân tích khung đầu. So sánh RGB không xét đầy đủ alpha, quản lý màu ICC hay định hướng hiển thị EXIF; không tự xoay hoặc căn chỉnh ảnh. Dữ liệu sau EOI, MAE cao hoặc hash khác không đủ để kết luận ảnh giả mạo. Chức năng JPEG/ML cũ giữ tương thích, không mở rộng Machine Learning trong giai đoạn này.

## Kết quả xác minh Giai đoạn 3

- Trước khi sửa: 38 passed trong 25,88 giây.
- Sau tích hợp: `python -m pytest -v` — 62 passed, 0 failed, 0 skipped trong 28,27 giây (Python 3.14.3, pytest 9.2.0).
- Batch Image2GPS-25: 100/100 thành công, 0 lỗi, 164,89 giây ở quality=90; 100 cấu trúc JPEG đạt kiểm tra cơ bản.
- Hash ban đầu/sau pipeline đều giữ nguyên; đối chiếu độc lập đủ 101 file gốc (100 ảnh + metadata.csv) đều không đổi.
- GUI đã kiểm tra Qt offscreen: QThread thật, progress/bảng batch, đưa kết quả sang Timeline, JPEG preview, ảnh sai khác/histogram, so sánh hai ảnh, kiểm tra lại hash và yêu cầu hủy. Giai đoạn 2 cũng kiểm thử lại QtWebEngine thật (chặn mạng trong bài kiểm thử).
- Kết quả máy đọc: outputs/stage3_validation.json; bảng đầy đủ: outputs/stage3_batch_100.csv; bảng hash: outputs/stage3_sha256_100.csv.

Thời gian là số đo tại môi trường chạy hiện tại, thay đổi theo ảnh, CPU, ổ đĩa và tải hệ thống. Kiểm thử offscreen chưa thay thế đánh giá thao tác trực tiếp trên màn hình Windows; không xác minh tải bản đồ nền trực tuyến.


## Giai đoạn 4: Machine Learning, thực nghiệm và PDF

### Cài đặt và chạy

Dùng môi trường .venv hiện có, không xóa/tạo lại và không chạy lại downloader:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe -m tests.experiment_stage4
```

ReportLab là dependency mới để xuất PDF; pypdf phục vụ kiểm thử nội dung và Unicode. PyMuPDF chỉ dùng khi render kiểm tra minh chứng tại môi trường phát triển, không cần để chạy ứng dụng. Không xây Deep Learning/CNN.

### Giao diện

Có đủ tám tab: Danh sách ảnh và Metadata, Batch Processing, JPEG Analysis, Tổng quan, GPS Map, Timeline, Anomaly Detection và Báo cáo. Vị trí ba tab cũ được giữ để không thay thao tác/kiểm thử hồi quy; ứng dụng mở tại Tổng quan. Anomaly Detection có hai tab con: Machine Learning / Phát hiện ngoại lệ và Cảnh báo theo quy tắc. GPS Map hiển thị bản đồ nhúng và có nút mở công cụ nhóm hành trình đã có. Timeline có bảng và bộ lọc riêng.

1. Nhập CSV từ Tổng quan hoặc tab Metadata. Có thể dùng Batch rồi đưa kết quả sang như trước.
2. Mở Anomaly Detection, chọn contamination, bấm Chạy Isolation Forest. Nếu còn thiếu đặc trưng ảnh, worker đọc ảnh thật để tính; giữ nguyên GPS/timestamp CSV và EXIF riêng. Kết quả Batch hợp lệ được tái sử dụng.
3. Bảng hiển thị Normal/Anomaly/Excluded, anomaly_score, decision_function, giá trị đặc trưng sau điền trung vị và các cột đã điền. Có tổng số theo nhãn và histogram điểm. Xuất CSV chỉ khi đã có kết quả; đổi bộ dữ liệu sẽ bỏ kết quả ML lỗi thời.
4. Mở Báo cáo, xuất PDF Unicode hoặc snapshot JSON. PDF dùng kết quả đã có; chưa chạy hash/JPEG/ML sẽ ghi rõ chưa phân tích, không suy đoán giá trị. ML/PDF chạy bằng QThread và có thanh tiến trình. Khi đang chạy, đóng cửa sổ yêu cầu kết thúc/hủy an toàn rồi đóng lại.

### Isolation Forest và đặc trưng

Bốn đặc trưng mặc định: file_bytes, width, height, jpeg_recompress_mae. Không dùng filename, nhãn, GPS, timestamp, vận tốc hay khoảng cách giữa các ảnh. Không xem 100 ảnh là một hành trình. Hiện chỉ cung cấp chế độ đặc trưng ảnh; không cung cấp chế độ ML GPS/thời gian.

Isolation Forest tạo 100 cây chia ngẫu nhiên theo đặc trưng. Điểm dễ cô lập sau ít lần chia thường khác biệt với phần lớn dữ liệu. random_state=42 cố định và n_jobs=1 giúp tái lập. contamination trong (0,0.5] xác định ngưỡng gắn nhãn theo tập huấn luyện, không chứng minh tỷ lệ ảnh giả mạo. Cần ít nhất 5 dòng hợp lệ và có biến thiên đặc trưng.

Dữ liệu rỗng, không hữu hạn, số đo âm hoặc kích thước/dung lượng bằng 0 được coi là thiếu. Dòng ảnh lỗi hoặc không có bất kỳ đặc trưng hợp lệ nào bị Excluded. Cột hoàn toàn thiếu ở tập train bị loại. Các giá trị còn thiếu được điền bằng trung vị chỉ học từ tập train; áp dụng lại trung vị đó khi predict, không học trung vị từ tập đánh giá. JPEG MAE=0 thực sự vẫn hợp lệ. Không chuẩn hóa vì phép chia theo trục của Isolation Forest không dựa vào khoảng cách Euclid giữa các đơn vị byte/pixel/MAE.

Quy ước ứng dụng: anomaly_score = -score_samples, càng lớn càng khác biệt; decision_function < 0 là Anomaly. Điểm không phải xác suất giả mạo. Tham khảo API chính thức: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html.

### Thực nghiệm và so sánh phương pháp

Dataset thật không có ground truth giả mạo: chỉ báo cáo số ngoại lệ và phân bố điểm, để Precision/Recall/F1/confusion matrix thật là null. Không tự gán nhãn ảnh thật/giả.

Thực nghiệm có kiểm soát dùng deepcopy: bản sao metadata có GPS ngoài phạm vi, timestamp sai và timestamp rỗng; bản sao đặc trưng có 3 dòng tăng các số đo theo hệ số 30/40/50. Không sửa ảnh hoặc CSV. Mô hình học trên đặc trưng gốc với contamination=0.1 cố định trước, rồi predict bản sao. Metric chỉ đánh giá nhãn can thiệp tổng hợp đã biết, không phải benchmark độc lập về giả mạo. Không điều chỉnh tham số theo kết quả đánh giá. Các dương tính trên bản gốc chưa can thiệp vẫn được tính là false positive đối với mục tiêu can thiệp tổng hợp.

| Phương pháp | Đầu vào / mục đích | Ưu điểm | Hạn chế |
|---|---|---|---|
| Quy tắc | GPS, thời gian, CSV/EXIF; kiểm tra hợp lệ/nhất quán | Mô tả được lỗi và giá trị/ngưỡng | Chỉ phát hiện điều đã mô tả; phụ thuộc metadata |
| Isolation Forest | Số đo từ ảnh; tìm khác biệt thống kê | Không cần nhãn giả mạo để fit | Phụ thuộc dữ liệu và contamination; không giải thích nguyên nhân hoặc chứng minh chỉnh sửa |

### PDF và minh chứng

PDF ReportLab nhúng Arial có dấu tiếng Việt (Windows) hoặc DejaVu Sans (Linux). Font không có sẽ báo lỗi rõ ràng. Báo cáo thao tác gồm đề tài, thời điểm lập UTC+07:00 (không phải timezone của ảnh), bộ dữ liệu, metadata/EXIF, GPS, Timeline, hash, JPEG, luật, ML nếu có, biểu đồ và giới hạn. Đây không phải báo cáo nghiên cứu hoàn chỉnh.

Toàn bộ minh chứng mới nằm trong outputs/stage4/: ml_results.csv, controlled_numeric_predictions.csv, controlled_metadata_alerts.csv, evaluation.json, features_records.json, report_snapshot.json, geoimage_forensics_report.pdf, timing_and_integrity.json, protected_manifest_before.json, protected_manifest_after.json, pytest_results.txt và thực nghiệm Markdown. Ảnh render PDF nằm trong pdf_preview/. Không sửa outputs/stage3_* hoặc outputs/chapter3_evidence/; nếu chapter3_evidence chưa tồn tại, kết quả ghi rõ không có thư mục này tại thời điểm chạy.

### Giới hạn

Mô hình là thăm dò trên tập đang phân tích, không dự đoán tính xác thực. Ít ảnh hoặc các đặc trưng giống nhau có thể không đủ để fit. Trung vị giảm ảnh hưởng của dữ liệu thiếu nhưng không phục hồi thông tin thật. Không có chế độ ML GPS/thời gian; không suy luận hành trình. ML trên CSV có thể cần tính JPEG MAE lần đầu nên mất thời gian; lần sau tái sử dụng kết quả trong phiên. Hủy ML có hiệu lực giữa các file khi thu thập đặc trưng, không ngắt giữa fit/PDF. Thống kê PDF phản ánh snapshot lúc xuất. GUI offscreen kiểm tra chức năng, chưa xác minh hiển thị bản đồ nền qua Internet.

## Kết quả xác minh Giai đoạn 4

- Baseline: 62 passed trong 28,55 giây.
- Lần kiểm thử cuối: 82 passed, 0 failed, 0 skipped trong 30,79 giây; 62 bài cũ không bị sửa/bỏ qua.
- Dataset 100 ảnh: 90 Normal, 10 Anomaly, 0 Excluded; không có ground truth ảnh thật/giả.
- Tính đặc trưng: 170,517 giây; ML: 0,089 giây; PDF: 0,193 giây; toàn thực nghiệm: 180,469 giây.
- Đối chiếu cuối 105 file dữ liệu/minh chứng: không có hash thay đổi. outputs/chapter3_evidence không tồn tại lúc chạy, không tạo/sửa/xóa thư mục đó.
- PDF 7 trang được render toàn bộ và kiểm tra Unicode; GUI offscreen hiển thị Arial tiếng Việt, rộng 1250 px, tám tab.
- pip check: No broken requirements found.
- Chi tiết: outputs/stage4/experiment_summary.md, final_validation.json, pytest_results.txt và geoimage_forensics_report.pdf.
