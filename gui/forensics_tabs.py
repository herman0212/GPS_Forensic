
import json
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                              QLabel, QLineEdit, QCheckBox, QSpinBox, QProgressBar,
                              QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox,
                              QTextEdit, QSplitter, QScrollArea)
from core.batch import list_images, run_batch, analyze_file, recheck_hashes
from core.integrity import annotate_duplicates
from core.jpeg_analysis import recompress_jpeg, compare_images
from core.metadata import export_rows


class AnalysisWorker(QThread):
    """Luồng nền chỉ tạo dữ liệu; mọi widget được cập nhật trên luồng GUI."""
    progress = Signal(int, int)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, arguments, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.arguments = arguments

    def run(self):
        try:
            if self.operation == 'batch':
                folder, recursive, quality = self.arguments
                paths = list_images(folder, recursive)
                self.progress.emit(0, len(paths))
                result = run_batch(paths, quality, self.isInterruptionRequested, self.progress.emit)
            elif self.operation == 'hash':
                result = recheck_hashes(self.arguments, self.isInterruptionRequested)
            elif self.operation == 'jpeg':
                path, quality = self.arguments
                result = {'record': analyze_file(path, quality), 'difference': None}
                if result['record']['success'] and result['record']['format'] == 'JPEG':
                    result['difference'] = recompress_jpeg(path, quality)
            else:
                result = compare_images(*self.arguments)
            self.result_ready.emit(result)
        except Exception as error:
            self.failed.emit(f'{type(error).__name__}: {error}')


def image_pixmap(image, width=450, height=240):
    """Sao chép buffer PIL sang Qt để không giữ con trỏ RAM đã giải phóng."""
    rgb = image.convert('RGB')
    qimage = QImage(rgb.tobytes(), rgb.width, rgb.height, rgb.width * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qimage).scaled(width, height, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation)


def histogram_pixmap(counts):
    """Vẽ histogram 256 mức |sai khác| bằng QPainter, không thêm thư viện."""
    pixmap = QPixmap(620, 190)
    pixmap.fill(QColor('white'))
    painter = QPainter(pixmap)
    painter.setPen(QColor('black'))
    painter.drawText(10, 18, 'Histogram |sai khác| RGB: trục X 0–255; trục Y số thành phần pixel')
    peak = max(counts) if counts else 0
    if peak:
        painter.setPen(QColor('#2468a0'))
        for index, count in enumerate(counts):
            x = 30 + int(index * 560 / 255)
            painter.drawLine(x, 160, x, 160 - int(125 * count / peak))
    painter.setPen(QColor('black'))
    painter.drawText(25, 182, '0')
    painter.drawText(565, 182, '255')
    painter.drawText(5, 35, str(peak))
    painter.end()
    return pixmap


class ForensicsTabs(QObject):
    """Điều khiển Batch Processing và JPEG Analysis, tách khỏi GPS/Timeline."""
    def __init__(self, window, accept_batch):
        super().__init__(window)
        self.window = window
        self.accept_batch = accept_batch
        self.worker = None
        self.rows = []
        self.batch_page = QWidget()
        self.jpeg_page = QWidget()
        self.make_batch_page()
        self.make_jpeg_page()

    def button(self, layout, title, action):
        button = QPushButton(title)
        button.clicked.connect(action)
        layout.addWidget(button)
        return button

    def make_batch_page(self):
        layout = QVBoxLayout(self.batch_page)
        controls = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setPlaceholderText('Thư mục ảnh')
        controls.addWidget(self.folder)
        self.choose_button = self.button(controls, 'Chọn thư mục', self.choose_folder)
        self.recursive = QCheckBox('Quét thư mục con')
        controls.addWidget(self.recursive)
        controls.addWidget(QLabel('JPEG quality:'))
        self.batch_quality = QSpinBox()
        self.batch_quality.setRange(1, 100)
        self.batch_quality.setValue(90)
        controls.addWidget(self.batch_quality)
        self.start_button = self.button(controls, 'Bắt đầu Batch', self.start_batch)
        self.cancel_button = self.button(controls, 'Hủy an toàn', self.cancel)
        self.cancel_button.setEnabled(False)
        layout.addLayout(controls)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        self.batch_status = QLabel('Chưa xử lý. Chỉ đọc dữ liệu gốc; hủy có hiệu lực giữa hai ảnh.')
        self.batch_status.setWordWrap(True)
        layout.addWidget(self.batch_status)
        actions = QHBoxLayout()
        self.hash_button = self.button(actions, 'Kiểm tra lại SHA-256', self.recheck)
        self.export_button = self.button(actions, 'Xuất kết quả Batch CSV', lambda: self.export(False))
        self.hash_export_button = self.button(actions, 'Xuất SHA-256 CSV', lambda: self.export(True))
        self.use_button = self.button(actions, 'Đưa kết quả sang Metadata / Timeline', self.use_results)
        layout.addLayout(actions)
        self.batch_table = QTableWidget()
        layout.addWidget(self.batch_table)
        layout.addWidget(QLabel('Cùng SHA-256 cho thấy trùng nội dung byte với độ tin cậy rất cao; không chứng minh cùng nguồn gốc chụp.'))

    def make_jpeg_page(self):
        outer = QVBoxLayout(self.jpeg_page)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('Chất lượng tái nén JPEG:'))
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(90)
        controls.addWidget(self.quality)
        self.jpeg_button = self.button(controls, 'Chọn ảnh để phân tích JPEG', self.choose_jpeg)
        self.compare_button = self.button(controls, 'Chọn hai ảnh để so sánh', self.choose_comparison)
        layout.addLayout(controls)
        note = QLabel('MAE không chứng minh chỉnh sửa. So sánh pixel chuẩn hóa RGB, không tự resize. Ảnh sai khác hiển thị được kéo giãn tương phản; histogram dùng giá trị thật.')
        note.setWordWrap(True)
        layout.addWidget(note)
        previews = QHBoxLayout()
        self.original_preview = QLabel('Ảnh gốc / ảnh thứ nhất')
        self.difference_preview = QLabel('Ảnh sai khác / ảnh thứ hai')
        for label in (self.original_preview, self.difference_preview):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setMinimumHeight(240)
            previews.addWidget(label)
        layout.addLayout(previews)
        self.histogram = QLabel('Histogram sai khác')
        layout.addWidget(self.histogram)
        self.jpeg_details = QTextEdit()
        self.jpeg_details.setReadOnly(True)
        self.jpeg_details.setMinimumHeight(230)
        layout.addWidget(self.jpeg_details)

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self.window, 'Chọn thư mục ảnh')
        if path:
            self.folder.setText(path)

    def start_batch(self):
        if not self.folder.text().strip():
            self.batch_status.setText('Hãy chọn thư mục ảnh.')
            return
        self.progress_bar.setRange(0, 0)
        self.batch_status.setText('Đang quét danh sách ảnh…')
        self.start_worker('batch', (self.folder.text(), self.recursive.isChecked(), self.batch_quality.value()))

    def start_worker(self, operation, arguments):
        if self.worker is not None and self.worker.isRunning():
            QMessageBox.information(self.window, 'Đang xử lý', 'Hãy chờ hoặc hủy tác vụ hiện tại.')
            return False
        self.worker = AnalysisWorker(operation, arguments, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.result_ready.connect(self.on_result)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.set_busy(True)
        self.worker.start()
        return True

    def set_busy(self, busy):
        for button in (self.start_button, self.hash_button, self.jpeg_button, self.compare_button,
                       self.export_button, self.hash_export_button, self.use_button):
            button.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)

    def cancel(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.requestInterruption()
            self.batch_status.setText('Đã yêu cầu hủy; chờ ảnh đang xử lý hoàn tất. Không sửa file gốc.')

    def on_progress(self, done, total):
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(done)
        self.batch_status.setText(f'Đã xử lý {done}/{total} ảnh…')

    def on_error(self, message):
        self.batch_status.setText(f'Lỗi tác vụ: {message}')
        self.jpeg_details.setPlainText(message)
        self.progress_bar.setRange(0, 1)

    def on_finished(self):
        self.set_busy(False)

    def on_result(self, result):
        operation = self.worker.operation
        if operation == 'batch':
            self.rows = result['rows']
            self.show_batch_rows()
            self.batch_status.setText(f'Tổng {result["total"]} | Đã xử lý {result["processed"]} | Thành công {result["succeeded"]} | Lỗi {result["failed"]} | Hủy: {result["cancelled"]} | {result["elapsed_seconds"]:.2f} giây')
            self.progress_bar.setRange(0, max(1, result['total']))
            self.progress_bar.setValue(result['processed'])
        elif operation == 'hash':
            # Khi hủy kiểm tra hash, giữ cả các hàng chưa kiểm tra trong bảng.
            checked = {row['path']: row for row in result}
            self.rows = [checked.get(row['path'], row) for row in self.rows]
            self.show_batch_rows()
            self.batch_status.setText(f'Đã kiểm tra lại hash {len(result)}/{len(self.rows)} file; xem cột trước/sau.')
        elif operation == 'jpeg':
            self.show_jpeg(result)
        else:
            self.show_comparison(result)

    def show_batch_rows(self):
        keys = ['file', 'path', 'success', 'format', 'size', 'mode', 'file_bytes', 'jpeg_recompress_mae',
                'sha256_before', 'sha256_after', 'hash_unchanged', 'same_content_count', 'same_name_count', 'error']
        labels = ['Tên', 'Đường dẫn', 'Thành công', 'Định dạng', 'Kích thước', 'Màu', 'Byte', 'JPEG MAE',
                  'SHA-256 trước', 'SHA-256 sau', 'Hash giữ nguyên', 'Cùng byte ban đầu', 'Số file cùng tên', 'Lỗi']
        self.batch_table.setColumnCount(len(keys))
        self.batch_table.setHorizontalHeaderLabels(labels)
        self.batch_table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            for j, key in enumerate(keys):
                value = row.get(key)
                item = QTableWidgetItem('' if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.batch_table.setItem(i, j, item)
        self.batch_table.resizeColumnsToContents()

    def recheck(self):
        if self.rows:
            self.start_worker('hash', self.rows)

    def use_results(self):
        if self.rows:
            self.accept_batch(self.rows)

    def export(self, hashes_only):
        if not self.rows:
            return
        path, _ = QFileDialog.getSaveFileName(self.window, 'Xuất CSV', 'outputs/sha256.csv' if hashes_only else 'outputs/batch.csv', 'CSV (*.csv)')
        if not path:
            return
        rows = self.rows
        if hashes_only:
            keys = ('file', 'path', 'sha256_before', 'sha256_after', 'hash_unchanged', 'same_content_count', 'same_name_count')
            rows = [{key: row.get(key) for key in keys} for row in rows]
        try:
            export_rows(rows, path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self.window, 'Lỗi xuất', str(error))

    def choose_jpeg(self):
        path, _ = QFileDialog.getOpenFileName(self.window, 'Chọn ảnh', '', 'Ảnh (*.jpg *.jpeg *.png *.tif *.tiff *.webp);;Tất cả (*)')
        if path:
            self.start_worker('jpeg', (path, self.quality.value()))

    def choose_comparison(self):
        paths, _ = QFileDialog.getOpenFileNames(self.window, 'Chọn đúng hai ảnh', '', 'Ảnh (*.jpg *.jpeg *.png *.tif *.tiff *.webp)')
        if len(paths) == 2:
            self.start_worker('compare', paths)
        elif paths:
            QMessageBox.information(self.window, 'So sánh', 'Cần chọn đúng hai ảnh.')

    def preview_file(self, label, path):
        # Thu nhỏ để xem, không sử dụng ảnh thu nhỏ để tính MAE.
        from PIL import Image
        try:
            with Image.open(path) as image:
                label.setPixmap(image_pixmap(image))
        except (OSError, ValueError):
            label.setText('Không đọc được ảnh')

    def show_jpeg(self, result):
        record = result['record']
        self.jpeg_details.setPlainText(json.dumps(record, ensure_ascii=False, indent=2))
        self.preview_file(self.original_preview, record['path'])
        self.difference_preview.setText('Không có sai khác JPEG: ảnh lỗi hoặc không phải JPEG.')
        self.histogram.clear()
        if result['difference'] is not None:
            difference = result['difference']
            self.difference_preview.setPixmap(image_pixmap(difference['difference_display']))
            self.histogram.setPixmap(histogram_pixmap(difference['histogram']))

    def show_comparison(self, result):
        self.jpeg_details.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        self.preview_file(self.original_preview, result['first']['path'])
        self.preview_file(self.difference_preview, result['second']['path'])
        self.histogram.setText('So sánh byte bằng SHA-256; pixel_mae so sánh RGB cùng kích thước. Không resize để tính toán.')

