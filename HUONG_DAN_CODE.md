# Hướng dẫn đọc mã Giai đoạn 1–4

1. main.py tạo QApplication và Window, sau đó vào vòng lặp sự kiện Qt.
2. gui/main_window.py kế thừa cửa sổ cũ để giữ nút chức năng. import_csv mở hộp chọn file rồi gọi load_dataset. refresh cập nhật bảng ảnh và Timeline. show_details hiển thị JSON nguồn CSV/EXIF riêng và ảnh xem trước. save_rows xử lý lỗi xuất CSV.
3. core/metadata.py: number loại dữ liệu không phải số hữu hạn; read_exif đọc IFD gốc, IFD EXIF lồng và GPS bằng Pillow. load_dataset kiểm tra cột bắt buộc theo CSV đã khảo sát, ngăn đường dẫn thoát khỏi images/, xử lý từng dòng dù ảnh lỗi. csv_original giữ nội dung gốc; trường latitude/timestamp hiển thị lấy CSV, không ghi vào EXIF. export_rows dùng JSON cho trường danh sách/dictionary trong CSV.
4. core/gps.py: valid_gps chỉ nhận vĩ độ [-90,90], kinh độ [-180,180] và số hữu hạn.
5. core/timeline.py: parse_time giữ offset; time_key chuẩn hóa thời gian có offset về UTC. build_timeline đếm thời gian trùng, sắp xếp hai nhóm, áp dụng bộ lọc và tính chênh lệch giây trong từng nhóm. Hai ảnh chưa rõ múi giờ chỉ được so sánh theo đồng hồ ghi nhận, không xác nhận chênh lệch thời gian thực tế.
6. core/legacy.py chứa mã thử nghiệm trước đó: SHA-256, JPEG MAE, xuất JSON/Folium và Isolation Forest. Đã bỏ suy đoán hành trình/tốc độ chỉ dựa cùng offset. Đây là phần giữ tương thích, sẽ được tách tiếp theo các giai đoạn sau.
7. tests/test_stage1.py dùng pytest với ảnh tạo trong thư mục tạm; không thay đổi ảnh dataset. Các ca kiểm tra GPS, timezone, thời gian trùng, CSV, ảnh mất, đường dẫn không hợp lệ, SHA-256 trước/sau và xuất CSV; cuối cùng nhập đủ 100 ảnh.
8. download_dataset.py là script tải cũ, không được tự chạy khi mở ứng dụng. Nó chuyển ảnh sang JPEG nên không thể coi CSV đi kèm là EXIF của JPEG.

Lệnh chạy: `.\.venv\Scripts\python.exe main.py`.
Lệnh kiểm thử: `.\.venv\Scripts\python.exe -m pytest -v`.

Giai đoạn 2 đã bổ sung Haversine và các luật GPS/thời gian. Giai đoạn 3 đã bổ sung QThread và JPEG; chưa bổ sung PDF hay ML mới. Không sử dụng kết quả thử nghiệm để kết luận giả mạo.


## Đọc mã bổ sung Giai đoạn 2

- gps.haversine: kiểm tra GPS, đổi radian, công thức đường tròn lớn R=6371 km. compare_positions trả distance_km, delta_seconds, speed_kmh, reason. Vận tốc cần journey_group giống nhau và giờ so sánh được; shared_clock là xác nhận do người dùng cung cấp cho giờ không offset.
- anomaly.analyze_rules: kiểm tra từng bản ghi, Counter đếm thời gian trùng sau chuẩn hóa offset, so EXIF/CSV. Tiếp theo nhóm theo journey_group và loại thời gian, sắp xếp rồi xét cặp liên tiếp. Không bỏ GPS lỗi ở giữa để nối giả hai đầu. Kết quả là hai danh sách mới, không sửa đầu vào. GPS CSV sai được đọc từ csv_original để phân biệt với thiếu dữ liệu.
- map_view.create_map: lọc GPS hợp lệ, escape tên ảnh và metadata, tạo marker/popup Folium; export_map lưu HTML. Không tự viết JavaScript hoặc nối hành trình.
- Window.open_gps_analysis: mở QDialog có bốn tab; assign_journey/clear_journey chỉnh ghi chú trong bộ nhớ. refresh_gps_analysis đọc ngưỡng, chạy luật và tạo HTML trong thư mục tạm, QWebEngineView.load dùng QUrl.fromLocalFile. LocalContentCanAccessRemoteUrls cho Folium tải Leaflet và bản đồ nền. Không dùng setHtml vì 100 marker có thể sinh HTML lớn.
- metadata.export_rows: hợp tất cả tên cột để vẫn xuất được khi chỉ một vài ảnh có journey_group.
- test_gps: vị trí trùng, khoảng cách biết trước, đối cực, đường đổi ngày, điều kiện vận tốc.
- test_anomaly: dữ liệu thiếu/sai/trùng, timezone, ngưỡng, GPS EXIF/CSV, nhóm, không sửa đầu vào.
- test_map: số marker, không nối đường, popup an toàn, xuất và tích hợp 100 ảnh không tự thành hành trình.
- test_gui_stage2: tạo QtWebEngine thật ở chế độ offscreen, chặn tải mạng, kiểm tra gán nhóm và chỉ có vận tốc sau xác nhận đồng hồ; bảng Giai đoạn 1 vẫn đủ 100 dòng.

Giai đoạn 3 được mô tả bên dưới; không triển khai Giai đoạn 4. Không mở rộng ML.


## Đọc mã Giai đoạn 3

1. core/integrity.py: sha256_file đọc từng khối 1 MiB rồi cập nhật hashlib.sha256. annotate_duplicates dùng Counter riêng cho hash trước và tên file; trả bản sao, không gộp hash rỗng. Hai bộ đếm tách ý nghĩa trùng nội dung khỏi trùng tên.
2. core/jpeg_analysis.py: inspect_jpeg_structure duy trì vị trí byte và trạng thái entropy. Segment nhảy theo length; entropy xử lý FF00, restart, TEM, DNL và marker chuyển scan. Không tìm toàn bộ chuỗi marker để kết luận cấu trúc. Trả markers có offset, missing, errors, trailing_bytes, structure_ok. Không tự coi DQT/DHT thiếu hay byte sau EOI là giả mạo.
3. pixel_mae kiểm tra hai mảng cùng shape, đổi kiểu số trước khi trừ rồi lấy trung bình trị tuyệt đối. recompress_jpeg dùng BytesIO, RGB và quality 1–100; trả ảnh sai khác thật, bản kéo giãn tương phản để xem và histogram. image_information gọi Pillow load để kiểm tra giải mã, đọc quantization, sampling và progressive. compare_images tách same_bytes khỏi pixel_mae; không resize.
4. core/batch.py: list_images dùng glob/rglob tùy chọn. analyze_file tính hash trước, nhận diện chữ ký JPEG, phân tích cấu trúc, đọc metadata/EXIF, MAE; try/except giữ lỗi theo file, finally cố đo hash sau kể cả khi ảnh hỏng. run_batch kiểm tra callback hủy giữa hai file, báo tiến trình và tổng kết thời gian. recheck_hashes đối chiếu với baseline giữ nguyên.
5. gui/forensics_tabs.py: AnalysisWorker là một QThread có progress/result_ready/failed. run không thao tác widget. ForensicsTabs tạo hai tab, xử lý signal trên GUI. Hủy bằng requestInterruption, không terminate. QPainter vẽ histogram thay vì thêm thư viện. image_pixmap sao chép buffer PIL sang QImage để tránh con trỏ trỏ vào bộ nhớ đã giải phóng. Ảnh chỉ thu nhỏ khi xem, không dùng ảnh thu nhỏ để tính MAE.
6. gui/main_window.py đưa giao diện cũ vào tab Metadata / Timeline, thêm Batch Processing và JPEG Analysis. load chuyển nút chọn thư mục cũ sang batch nền. accept_batch_results chỉ thay bộ metadata đang xem khi người dùng bấm nút đưa kết quả. closeEvent không đóng khi QThread còn đang chạy; yêu cầu hủy an toàn trước.
7. core/legacy.py: digest và inspect_image chuyển sang gọi module SHA-256/Batch chung, bỏ cách tính JPEG MAE trùng lặp. Các chức năng GPS và ML cũ còn được giữ tương thích; không xây ML mới.
8. tests/test_batch.py: mẫu hash abc, file nhiều khối, thư mục rỗng, lỗi từng ảnh, định dạng, thư mục con, trùng tên/byte, hủy, hash đổi và mất file. tests/test_jpeg_analysis.py: baseline/progressive, cắt file, byte sau EOI, marker giả trong segment/entropy, byte stuffing/restart, MAE và hash bảo toàn. tests/test_gui_stage3.py kiểm tra worker thật, các bảng, ảnh sai khác/histogram, so sánh và hủy trên Qt offscreen.
9. tests/benchmark_stage3.py: chạy bằng -m tests.benchmark_stage3, đo 100 ảnh; đối chiếu 101 file gốc (100 ảnh + CSV), ghi CSV và JSON vào outputs. Không sửa dataset.

Đọc README phần Giai đoạn 3 để biết thao tác và giới hạn. Không suy luận giả mạo chỉ từ cảnh báo JPEG hoặc hash.


## Đọc mã Giai đoạn 4

- core/machine_learning.py: numeric_feature kiểm tra số đo. prepare_features tạo ma trận bốn cột và giữ chỉ số dòng, không dùng tên ảnh làm input. train_model loại cột hoàn toàn thiếu, học median, fit IsolationForest 100 cây/random_state=42. predict_model tái sử dụng median train, trả Normal/Anomaly/Excluded và score. run_isolation_forest gộp các bước và đo thời gian. evaluate_labels chỉ tính metric cho hai dãy nhãn 0/1 có mục tiêu rõ ràng.
- core/stage4_analysis.py: collect_features đọc ảnh còn thiếu số đo trên bản sao, ghép trường ảnh/EXIF nhưng giữ timestamp/GPS CSV. dataset_signature băm trạng thái trong RAM để gỡ kết quả ML khi bộ ảnh thay đổi; đây không thay thế SHA-256 của file ảnh.
- core/experiments.py: controlled_experiment sao chép dữ liệu, tạo riêng lỗi metadata và đặc trưng số tăng có kiểm soát, fit dữ liệu gốc rồi predict bản sao với tham số đã cố định. Nhãn chỉ là nhãn can thiệp. So sánh định tính luật và ML có trong kết quả.
- core/reporting.py: protect_output chặn ghi lên data, file nguồn và minh chứng Giai đoạn 3. build_report thống kê snapshot và đánh dấu chưa phân tích thay vì tạo kết quả. register_fonts nhúng font Unicode. bar_chart tạo biểu đồ vector. export_pdf dùng ReportLab Platypus cho ngắt trang, bảng lặp header và footer; không yêu cầu JavaScript.
- gui/stage4_tabs.py: Stage4Worker là QThread cho thu thập đặc trưng/ML hoặc PDF. Stage4Tabs tạo Tổng quan, GPS Map, Anomaly Detection và Báo cáo. run_ml chụp snapshot; on_result kiểm tra signature để không hiển thị nhầm nếu bộ ảnh đổi. snapshot chỉ gắn ML vào bộ dữ liệu tương ứng. score_chart vẽ histogram bằng QPainter. Xuất CSV/JSON/PDF có thông báo thiếu dữ liệu.
- gui/main_window.py: giữ ba tab cũ, tách Timeline sang tab riêng, thêm bốn tab Giai đoạn 4 thành tám tab. Giữ chỉ số ba tab cũ để các thao tác/kiểm thử cũ không đổi; khởi động tại Tổng quan. Nút ML cũ chuyển sang mô hình đặc trưng ảnh. closeEvent bảo vệ worker của cả Batch và Giai đoạn 4.
- tests/test_machine_learning.py: chọn đặc trưng, thiếu dữ liệu, median train, cột thiếu hoàn toàn, contamination, ít dữ liệu, score/tái lập, metric kiểm chứng được và CSV.
- tests/test_reporting.py: chưa phân tích không bị tự điền kết quả, PDF Unicode/ToUnicode, không có ML, từ chối ML không cùng bộ ảnh và bảo toàn hash khi tính đặc trưng.
- tests/test_gui_stage4.py: tám tab, worker ML/PDF thật trên Qt offscreen, biểu đồ, PDF và loại kết quả lỗi thời sau khi metadata đổi.
- tests/experiment_stage4.py: thực nghiệm đủ 100 ảnh, tính đặc trưng thật, lưu kết quả/metric/PDF/timing trong outputs/stage4 và đối chiếu hash của data, outputs/stage3_* và chapter3_evidence nếu có. stdout UTF-8 để chạy được trên console Windows có mã hóa mặc định khác.

Trình tự bảo vệ đồ án: giải thích nguồn CSV/EXIF -> luật GPS/thời gian -> đặc trưng ảnh -> Isolation Forest -> điểm/nhãn ngoại lệ -> thí nghiệm bản sao -> báo cáo và các giới hạn. Không trình bày metric nhãn can thiệp như độ chính xác phát hiện giả mạo.
