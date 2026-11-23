# GeoImageForensics

**Demo phân tích ảnh số và kiểm tra tính nhất quán của metadata GPS bằng Python.**

GeoImageForensics phục vụ đề tài **Nghiên cứu kỹ thuật Image Forensics và xây dựng chương trình bằng Python hỗ trợ phân tích ảnh số**.

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
| Batch Processing | Phân tích nhiều ảnh trên luồng nền, hiển thị tiến trình, thống kê lỗi và hủy an toàn |
| SHA-256 | Tính hash, đối chiếu trước/sau, nhận diện file trùng nội dung và xuất bảng kết quả |
| JPEG Analysis | Kiểm tra cấu trúc JPEG, tái nén trong bộ nhớ, tính MAE, hiển thị ảnh sai khác và histogram |
| So sánh ảnh | So sánh thông tin file, hash và pixel RGB khi hai ảnh cùng kích thước |
| Machine Learning | Isolation Forest phát hiện ảnh có đặc trưng thống kê khác biệt trong tập đang xét |
| Báo cáo | Xuất CSV, JSON, HTML và PDF tiếng Việt từ các kết quả đã phân tích |

## Công nghệ sử dụng

- **Python**: xử lý dữ liệu và các thuật toán phân tích.
- **PySide6 / QtWebEngine**: giao diện desktop và bản đồ nhúng.
- **Pillow, NumPy**: đọc EXIF, xử lý ảnh và tính toán pixel.
- **Folium**: tạo bản đồ từ các tọa độ hợp lệ.
- **scikit-learn**: mô hình Isolation Forest.
- **ReportLab**: xuất báo cáo PDF hỗ trợ tiếng Việt.
- **pytest**: kiểm thử các chức năng.

Dự án được phát triển trên Windows với Python 3.14.3. Các thư viện cần thiết được liệt kê trong [requirements.txt](requirements.txt).

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

CSV sử dụng các cột sau:

```text
filename,img_id,lat,lon,gps_altitude,timestamp,timestamp_raw,camera_make,camera_model,split
```

Khi một nguồn GPS thiếu hoặc không hợp lệ, kết quả đối chiếu là **chưa đủ dữ liệu**; chương trình không tự lấy tọa độ của nguồn khác để điền vào.

### 2. Phân tích thư mục ảnh

Mở **Batch Processing**, chọn thư mục, tùy chọn quét thư mục con và bắt đầu phân tích. Sau khi hoàn tất, có thể xem bảng kết quả, kiểm tra hash hoặc xuất CSV.

**Batch chỉ đọc ảnh và EXIF, không tự nhập CSV.** Nút **Đưa kết quả sang Metadata / Timeline** thay bộ ảnh đang xem bằng kết quả Batch. Muốn đối chiếu EXIF/CSV, hãy nhập `metadata.csv` trực tiếp; nếu đã chuyển kết quả Batch sang thì nhập lại CSV.

### 3. JPEG, ngoại lệ thống kê và báo cáo

- Dùng **JPEG Analysis** để xem cấu trúc JPEG, MAE, ảnh sai khác hoặc so sánh hai ảnh.
- Dùng **Anomaly Detection** để xem cảnh báo theo quy tắc hoặc chạy Isolation Forest trên đặc trưng ảnh.
- Dùng **Báo cáo** để xuất PDF/JSON; kết quả chưa được phân tích sẽ được ghi rõ thay vì tự suy đoán.
- Bản đồ có thể xuất ra HTML. Việc tải thư viện và bản đồ nền cần kết nối Internet phù hợp.

## Dữ liệu phục vụ demo

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

Các bài kiểm thử bao phủ GPS/EXIF/CSV, Timeline, bản đồ, Batch, SHA-256, JPEG, ML, xuất báo cáo và tích hợp GUI. Dữ liệu thử được tạo riêng; không sửa dataset gốc để làm cho kiểm thử đạt.

## Nguyên tắc và giới hạn

- Phân tích chỉ đọc ảnh và CSV nguồn; không ghi EXIF vào ảnh gốc. Nên lưu kết quả mới vào file/thư mục đầu ra riêng.
- GPS CSV và GPS EXIF là hai nguồn độc lập; khớp nhau không chứng minh cả hai đáng tin cậy.
- Ngưỡng sai lệch tọa độ là cấu hình kỹ thuật, không phải tiêu chuẩn xác nhận giả mạo.
- Nếu GPS bị đổi thành tọa độ vẫn hợp lệ mà không có nguồn tham chiếu đáng tin cậy, chương trình có thể không phát hiện.
- Timestamp thiếu múi giờ được giữ nguyên, không tự gán UTC hoặc giờ Việt Nam.
- SHA-256 giúp kiểm tra nội dung byte, không chứng minh nguồn gốc chụp ảnh.
- MAE cao, dữ liệu sau EOI hoặc nhãn **Anomaly** không tự chứng minh ảnh đã bị chỉnh sửa.
- Isolation Forest phục vụ quan sát ngoại lệ thống kê, không phải mô hình xác thực ảnh thật/giả.
- Demo phục vụ học tập và thực nghiệm; không thay thế quy trình giám định pháp chứng chuyên nghiệp.

Các kết quả lịch sử trong `outputs/` phản ánh từng lần chạy và phiên bản tương ứng. Không dùng chúng để mặc định rằng giao diện hoặc chức năng hiện tại giống hệt phiên bản cũ.
