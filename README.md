# GeoImageForensics

**Demo phân tích ảnh số và kiểm tra tính nhất quán của metadata GPS bằng Python.**

GeoImageForensics là ứng dụng desktop phục vụ đề tài **Nghiên cứu kỹ thuật Image Forensics và xây dựng chương trình bằng Python hỗ trợ phân tích ảnh số**. Chương trình được xây dựng theo hướng dễ đọc, dễ sử dụng và phù hợp.

Ứng dụng kết hợp thông tin từ ảnh, EXIF và metadata CSV để hỗ trợ người dùng quan sát dữ liệu, phát hiện dấu hiệu cần kiểm tra và xuất kết quả phân tích.

## Mục tiêu demo

- Tìm hiểu metadata và các đặc điểm kỹ thuật của ảnh số.
- Phân biệt dữ liệu EXIF trong ảnh với metadata được cung cấp từ CSV.
- Kiểm tra tính hợp lệ và tính nhất quán của thông tin GPS, thời gian.
- Minh họa SHA-256, phân tích JPEG và phát hiện ngoại lệ thống kê.
- Tạo kết quả có thể đối chiếu, kiểm thử và sử dụng trong báo cáo thực nghiệm.

## Chức năng chính

| Nhóm chức năng | Nội dung |
|---|---|
| Metadata và xem ảnh | Nhập CSV, ghép ảnh theo tên file, đọc EXIF, xem ảnh và thông tin liên quan |
| GPS Forensics | Kiểm tra tọa độ, phân biệt nguồn CSV/EXIF, đối chiếu từng thành phần tọa độ theo ngưỡng dung sai |
| GPS Map | Hiển thị tọa độ hợp lệ trên Folium, tách lớp theo nguồn và xuất bản đồ HTML |
| Timeline | Sắp xếp, lọc thời gian; nhận diện timestamp thiếu, sai, trùng hoặc chưa rõ múi giờ |
| Batch Processing | Phân tích tuần tự nhiều ảnh trong luồng nền, hiển thị tiến trình, thống kê lỗi và hủy giữa các ảnh |
| SHA-256 | Tính hash, đối chiếu trước/sau, nhận diện file trùng nội dung và xuất bảng kết quả |
| JPEG Analysis | Kiểm tra cấu trúc JPEG, tái nén trong bộ nhớ, tính MAE, hiển thị ảnh sai khác và histogram |
| So sánh ảnh | So sánh thông tin file và hash; tính thêm MAE pixel RGB khi hai ảnh cùng kích thước |
| Machine Learning | Isolation Forest tìm ngoại lệ từ dung lượng, chiều rộng, chiều cao và MAE tái nén; không dùng GPS/timestamp làm đầu vào |
| Xuất kết quả | CSV cho bảng dữ liệu, JSON cho điều tra/báo cáo, HTML cho bản đồ và PDF tiếng Việt cho báo cáo tổng hợp |

### Phạm vi định dạng

Batch quét các phần mở rộng `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff` và `.webp`. Pillow đọc nội dung để xác định định dạng thực tế, kích thước và chế độ màu. EXIF chỉ được trích xuất khi có và thư viện đọc được; SHA-256 được tính trước/sau khi có thể đọc tập tin. Tập tin lỗi được ghi nhận riêng, không mặc định thành công chỉ vì có phần mở rộng ảnh.

Kiểm tra cấu trúc JPEG và tái nén/MAE JPEG chỉ áp dụng cho JPEG. Thực nghiệm chính dùng 100 JPEG; bài kiểm thử Batch có JPEG, PNG và TIFF tạm. WebP được hỗ trợ trong mã nhưng chưa có bài kiểm thử riêng, nên chưa khẳng định đã kiểm chứng đầy đủ WebP.

## Công nghệ sử dụng

- **Python**: xử lý dữ liệu và các thuật toán phân tích.
- **PySide6 / QtWebEngine**: giao diện desktop và bản đồ nhúng.
- **Pillow, NumPy**: đọc EXIF, xử lý ảnh và tính toán pixel.
- **Folium**: tạo bản đồ từ các tọa độ hợp lệ.
- **scikit-learn**: mô hình Isolation Forest.
- **ReportLab**: xuất báo cáo PDF hỗ trợ tiếng Việt.
- **pytest**: kiểm thử các chức năng.

Dự án được phát triển trên Windows với Python 3.14.3. Các thư viện cần thiết được liệt kê trong [requirements.txt](requirements.txt).

Luồng phân tích hiện tại dùng Pillow để đọc EXIF, không yêu cầu ExifTool. Tiện ích `download_dataset.py` sử dụng thêm thư viện `datasets`, không được liệt kê trong `requirements.txt`; đây là tiện ích chuẩn bị dữ liệu riêng, không cần chạy khi dữ liệu đã có.

## Cài đặt và khởi chạy

Mở PowerShell tại thư mục dự án:

```powershell
cd D:\GeoImageForensics
```

Nếu chưa có môi trường ảo, tạo bằng lệnh sau. Nếu `.venv` đã tồn tại thì sử dụng môi trường hiện có, không cần tạo lại.

```powershell
python -m venv .venv
```

Cài thư viện và chạy ứng dụng:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Hướng dẫn sử dụng nhanh

### 1. Phân tích dữ liệu có CSV

1. Chọn **Nhập Dataset CSV**.
2. Mở file `metadata.csv`; các ảnh tương ứng cần nằm trong thư mục `images/` cạnh file CSV.
3. Xem danh sách ảnh, metadata và Timeline.
4. Mở **GPS Forensics Investigation** để đối chiếu GPS CSV với GPS EXIF.
5. Chọn ngưỡng dung sai và cập nhật kết quả. Mặc định là **0.0001 độ tọa độ**.

CSV của bộ demo hiện có sử dụng các cột sau:

```text
filename,img_id,lat,lon,gps_altitude,timestamp,timestamp_raw,camera_make,camera_model,split
```

Hàm nhập bắt buộc tám cột `filename`, `lat`, `lon`, `gps_altitude`, `timestamp`, `timestamp_raw`, `camera_make`, `camera_model`. `img_id` và `split` là cột bổ sung của bộ demo. Tên ảnh phải nằm trực tiếp trong `images/`, không chứa đường dẫn thư mục con. Nếu `timestamp` rỗng, hàm nhập thử dùng `timestamp_raw`; timestamp CSV sai không tự được thay bằng timestamp EXIF.

Khi một nguồn GPS thiếu hoặc không hợp lệ, kết quả đối chiếu là **chưa đủ dữ liệu**; chương trình không tự lấy tọa độ của nguồn khác để điền vào.

Chỉ khi cả hai nguồn hợp lệ, chương trình so `abs(lat_csv - lat_exif)` và `abs(lon_csv - lon_exif)` với ngưỡng. Không tính khoảng cách, vận tốc hoặc suy luận hành trình; bản đồ không tự nối các điểm GPS.

### 2. Phân tích thư mục ảnh

Mở **Batch Processing**, chọn thư mục, tùy chọn quét thư mục con và bắt đầu phân tích. Sau khi hoàn tất, có thể xem bảng kết quả, kiểm tra hash hoặc xuất CSV.

QThread chạy tác vụ nền; ảnh vẫn được xử lý lần lượt, không phải nhiều ảnh song song. Hủy có hiệu lực giữa hai ảnh. Hash trùng hỗ trợ kiểm tra byte giữ nguyên giữa các lần đo; không xác minh lịch sử ảnh trước mốc hash ban đầu. Lỗi đọc hoặc thiếu hash không được diễn giải thành chắc chắn nội dung đã thay đổi.

**Batch chỉ đọc ảnh và EXIF, không tự nhập CSV.** Nút **Đưa kết quả sang Metadata / Timeline** thay bộ ảnh đang xem bằng kết quả Batch. Muốn đối chiếu EXIF/CSV, hãy nhập `metadata.csv` trực tiếp; nếu đã chuyển kết quả Batch sang thì nhập lại CSV.

### 3. JPEG, ngoại lệ thống kê và báo cáo

- Dùng **JPEG Analysis** để xem cấu trúc JPEG, MAE, ảnh sai khác hoặc so sánh hai ảnh.
- Dùng **Anomaly Detection** để xem cảnh báo theo quy tắc hoặc chạy Isolation Forest trên đặc trưng ảnh.
- Dùng **Báo cáo** để xuất PDF/JSON; kết quả chưa được phân tích sẽ được ghi rõ thay vì tự suy đoán.
- Bản đồ có thể xuất ra HTML. Việc tải thư viện và bản đồ nền cần kết nối Internet phù hợp.

MAE JPEG mặc định được tính với quality 90, có thể đổi trong giao diện. Ảnh sai khác hiển thị được tăng tương phản; MAE và histogram dùng sai khác gốc. So sánh hai ảnh không tự resize để ép cùng kích thước.

Isolation Forest dùng `file_bytes`, `width`, `height`, `jpeg_recompress_mae`; tối thiểu cần năm bản ghi phù hợp và đặc trưng có biến thiên. Mặc định: 100 cây, contamination 0.1, random_state 42. Điểm `anomaly_score = -score_samples` càng lớn càng khác biệt, không phải xác suất giả mạo. `Excluded` nghĩa là bản ghi không đủ điều kiện dự đoán. Chạy ML có thể đọc thêm ảnh để bổ sung đặc trưng, không ghi đè GPS/timestamp CSV bằng EXIF.

Muốn báo cáo có mô hình, chạy ML trước rồi xuất ở tab **Báo cáo**. Snapshot PDF/JSON tại tab này dùng dữ liệu đã bổ sung đặc trưng khi có; CSV/JSON metadata hoặc JSON điều tra GPS là những đầu ra khác, không mặc định chứa đầy đủ ML/hash/JPEG. Khi đổi bộ bản ghi đang phân tích, cần chạy lại mô hình. Thời điểm lập báo cáo UTC+07:00 không phải múi giờ được gán cho ảnh.

## Dữ liệu phục vụ demo

Ảnh/CSV của Image2GPS-25 và toàn bộ `outputs/` đang bị `.gitignore` loại khỏi Git. Các đường dẫn dưới đây là dữ liệu cục bộ, không bảo đảm có sẵn khi clone repository sang máy khác. Cần chuẩn bị riêng dữ liệu trước khi demo và trước khi chạy những bài kiểm thử dùng dataset thật.

### Image2GPS-25

```text
data/Image2GPS25/
├── images/
└── metadata.csv
```

Bộ dữ liệu hiện có gồm 100 JPEG đã được chuyển đổi bằng Pillow. Các ảnh không có GPS EXIF gốc; thông tin vị trí được cung cấp riêng qua CSV. Timestamp CSV không có thông tin múi giờ.

Bộ này phù hợp để minh họa nhập dữ liệu, xem ảnh, kiểm tra metadata và xử lý hàng loạt. Không kỳ vọng đối chiếu được hai nguồn GPS khi ảnh không có GPS EXIF. Không cần chạy lại `download_dataset.py` nếu dữ liệu đã có.

### Bộ GPS thực nghiệm có kiểm soát

```text
outputs/gps_forensics/demo_evidence/experiments/
├── images/GPS-01.jpg ... GPS-08.jpg
├── metadata.csv
├── expected_results.csv
├── verification_results.csv
├── create_gps_experiments.py
└── README.md
```

Tám JPEG thử nghiệm có các tình huống: hai nguồn GPS khớp, sai lệch trong/vượt ngưỡng, thiếu GPS từng nguồn, tọa độ CSV ngoài phạm vi và timestamp CSV không hợp lệ.

Để trình diễn bộ này, nhập file CSV trong thư mục trên. Đây là **dữ liệu thực nghiệm có kiểm soát**, không phải bằng chứng ảnh bị giả mạo ngoài thực tế. Xem [hướng dẫn bộ thử nghiệm](outputs/gps_forensics/demo_evidence/experiments/README.md) để biết kỳ vọng từng trường hợp.

## Cấu trúc dự án

```text
GeoImageForensics/
├── main.py                # Điểm khởi chạy
├── core/                  # Metadata, GPS, Timeline, hash, JPEG, ML và báo cáo
├── gui/                   # Giao diện PySide6
├── tests/                 # Kiểm thử và tiện ích thực nghiệm
├── data/                  # Dataset gốc
├── outputs/               # Kết quả phân tích và minh chứng
├── download_dataset.py    # Tiện ích tải dữ liệu
├── requirements.txt
├── HUONG_DAN_CODE.md
└── README.md
```

Giải thích từng module và các hàm quan trọng nằm trong [HUONG_DAN_CODE.md](HUONG_DAN_CODE.md).

## Kiểm thử

Chạy toàn bộ bộ kiểm thử:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Các bài kiểm thử kiểm tra GPS/EXIF/CSV, Timeline, bản đồ, Batch, SHA-256, JPEG, ML, xuất báo cáo và tích hợp GUI. Phần lớn dùng dữ liệu trong thư mục tạm; một số bài đọc bộ 100 ảnh ở `data/Image2GPS25/`. Không sửa dataset gốc để làm cho kiểm thử đạt. Danh sách nhóm kiểm thử không phải chỉ số phần trăm bao phủ mã nguồn.

Kiểm thử GUI dùng Qt offscreen và thay thế một số thao tác chọn file/tải bản đồ. Kết quả không thay thế kiểm tra thủ công trên desktop hoặc xác nhận bản đồ nền tải qua mạng. Log và số đo đã lưu chỉ phản ánh lần chạy tương ứng, không tự được xác minh lại mỗi lần mở tài liệu.

## Nguyên tắc và giới hạn

- Phân tích chỉ đọc ảnh và CSV nguồn; không ghi EXIF vào ảnh gốc. Luôn lưu kết quả vào đầu ra riêng: một số hàm xuất có chặn đường dẫn nguồn, nhưng không phải mọi thao tác xuất đều có cùng cơ chế bảo vệ. Không chọn ghi đè dữ liệu hoặc minh chứng cũ.
- GPS CSV và GPS EXIF được lưu tách biệt; không mặc định chúng độc lập hoặc đáng tin cậy. Khớp nhau không chứng minh vị trí chụp.
- Ngưỡng sai lệch tọa độ là cấu hình kỹ thuật, không phải tiêu chuẩn xác nhận giả mạo.
- Nếu GPS bị đổi thành tọa độ vẫn hợp lệ mà không có nguồn tham chiếu đáng tin cậy, chương trình có thể không phát hiện.
- Timestamp thiếu múi giờ được giữ nguyên, không tự gán UTC hoặc giờ Việt Nam.
- SHA-256 giúp kiểm tra nội dung byte, không chứng minh nguồn gốc chụp ảnh.
- MAE cao, dữ liệu sau EOI hoặc nhãn **Anomaly** không tự chứng minh ảnh đã bị chỉnh sửa.
- Isolation Forest phục vụ quan sát ngoại lệ thống kê, không phải mô hình xác thực ảnh thật/giả.
- ML thông thường học và dự đoán trên cùng tập ảnh, mang tính thăm dò. Contamination là tham số ngưỡng, không phải tỷ lệ ảnh giả đã xác nhận. Chỉ số trên can thiệp tổng hợp chỉ có ý nghĩa với can thiệp đó, không phải độ chính xác phát hiện giả mạo thực tế.
- Chỉ có một nguồn GPS hợp lệ vẫn có thể hiển thị marker nhưng chưa đủ đối chiếu hai nguồn. Số ảnh có nguồn GPS hợp lệ và số ảnh có nguồn sai có thể giao nhau.
- Demo phục vụ học tập và thực nghiệm; không thay thế quy trình giám định pháp chứng chuyên nghiệp.

Các kết quả lịch sử trong `outputs/` phản ánh từng lần chạy và phiên bản tương ứng. Không dùng chúng để mặc định rằng giao diện hoặc chức năng hiện tại giống hệt phiên bản cũ.
