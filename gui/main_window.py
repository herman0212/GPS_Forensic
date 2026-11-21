"""Giao diện Giai đoạn 1 mở rộng cửa sổ thử nghiệm hiện có."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QFont, QFontDatabase
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QPushButton, QLabel, QLineEdit,
                              QTableWidget, QTableWidgetItem, QDialog, QVBoxLayout,
                              QHBoxLayout, QTabWidget, QDoubleSpinBox, QWidget, QApplication)
from pathlib import Path
from tempfile import TemporaryDirectory
from core.legacy import Window as LegacyWindow
from core.metadata import load_dataset, export_rows
from core.reporting import protect_output
import json
from core.timeline import build_timeline
from core.gps import validate_tolerance
from core.anomaly import analyze_rules
from core.map_view import export_map
from gui.forensics_tabs import ForensicsTabs
from gui.stage4_tabs import Stage4Tabs


class Window(LegacyWindow):
    """Bổ sung nhập CSV, ảnh xem trước và bảng thời gian riêng."""
    def __init__(self):
        # Qt offscreen có thể không tự tìm font hệ thống. Nạp Arial Unicode
        # rõ ràng để cả widget và biểu đồ hiển thị tiếng Việt nhất quán.
        for font_path in ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf',
                          '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'):
            if Path(font_path).is_file():
                font_id = QFontDatabase.addApplicationFont(font_path)
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    QApplication.instance().setFont(QFont(families[0], 10))
        super().__init__()
        layout = self.centralWidget().layout()
        button = QPushButton('Nhập Dataset CSV')
        button.clicked.connect(self.import_csv)
        layout.itemAt(0).layout().insertWidget(0, button)
        self.preview = QLabel('Chọn ảnh để xem; chi tiết phân biệt CSV và EXIF')
        layout.addWidget(self.preview)
        self.start = QLineEdit()
        self.end = QLineEdit()
        self.start.setPlaceholderText('Từ: ISO 8601 (có thể bỏ trống)')
        self.end.setPlaceholderText('Đến: ISO 8601 (có thể bỏ trống)')
        layout.addWidget(self.start)
        layout.addWidget(self.end)
        for label, action in [('Lọc Timeline', self.update_timeline), ('Xuất Timeline CSV', self.export_timeline)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            layout.addWidget(button)
        self.timeline_table = QTableWidget()
        layout.addWidget(self.timeline_table)
        self.timeline_rows = []
        button = QPushButton('GPS Forensics Investigation')
        button.clicked.connect(self.open_gps_analysis)
        layout.itemAt(0).layout().addWidget(button)
        # Chia thanh nút thành hai hàng để không ép cửa sổ rộng hơn màn hình.
        old_bar = layout.takeAt(0).layout()
        toolbar = QVBoxLayout()
        first_row, second_row = QHBoxLayout(), QHBoxLayout()
        toolbar.addLayout(first_row)
        toolbar.addLayout(second_row)
        count = 0
        while old_bar.count():
            item = old_bar.takeAt(0)
            if item.widget() is not None:
                (first_row if count < 4 else second_row).addWidget(item.widget())
                count += 1
        layout.insertLayout(0, toolbar)
        old_bar.deleteLater()
        self.gps_dialog = None
        self.map_directory = TemporaryDirectory(prefix='geoimage-map-')
        # Đưa giao diện cũ nguyên vẹn vào tab để GPS/Timeline không bị xáo trộn.
        metadata_page = self.takeCentralWidget()
        self.workspace_tabs = QTabWidget()
        self.workspace_tabs.addTab(metadata_page, 'Metadata / Timeline')
        self.forensics = ForensicsTabs(self, self.accept_batch_results)
        self.workspace_tabs.addTab(self.forensics.batch_page, 'Batch Processing')
        self.workspace_tabs.addTab(self.forensics.jpeg_page, 'JPEG Analysis')
        self.setCentralWidget(self.workspace_tabs)
        self.stage4 = Stage4Tabs(self)
        # Giữ vị trí ba tab cũ để các thao tác và kiểm thử hồi quy không đổi.
        self.workspace_tabs.setTabText(0, 'Danh sách ảnh và Metadata')
        self.workspace_tabs.addTab(self.stage4.overview_page, 'Tổng quan')
        self.workspace_tabs.addTab(self.stage4.map_page, 'GPS Map')
        self.timeline_page = QWidget()
        timeline_layout = QVBoxLayout(self.timeline_page)
        for widget in (self.start, self.end):
            timeline_layout.addWidget(widget)
        for button in metadata_page.findChildren(QPushButton):
            if button.text() in ('Lọc Timeline', 'Xuất Timeline CSV'):
                timeline_layout.addWidget(button)
        timeline_layout.addWidget(self.timeline_table)
        self.workspace_tabs.addTab(self.timeline_page, 'Timeline')
        self.workspace_tabs.addTab(self.stage4.anomaly_page, 'Anomaly Detection')
        self.workspace_tabs.addTab(self.stage4.report_page, 'Báo cáo')
        self.workspace_tabs.currentChanged.connect(self.activate_analysis_tab)
        self.workspace_tabs.setCurrentWidget(self.stage4.overview_page)
        self.stage4.refresh()
        self.resize(1250, 950)

    def activate_analysis_tab(self, index):
        page = self.workspace_tabs.widget(index)
        if page is self.stage4.map_page:
            self.stage4.update_map()
        elif page in (self.stage4.overview_page, self.stage4.anomaly_page):
            self.stage4.refresh()

    def load(self):
        """Nút chọn thư mục cũ chuyển sang Batch trên luồng nền."""
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh')
        if folder:
            self.forensics.folder.setText(folder)
            self.workspace_tabs.setCurrentWidget(self.forensics.batch_page)
            self.forensics.start_batch()

    def accept_batch_results(self, rows):
        """Chỉ thay bộ ảnh đang xem khi người dùng bấm đưa kết quả sang."""
        self.records = [dict(row) for row in rows]
        self.start.clear()
        self.end.clear()
        self.refresh()
        self.workspace_tabs.setCurrentIndex(0)

    def closeEvent(self, event):
        """Không hủy QThread cưỡng bức khi đóng cửa sổ."""
        if self.forensics.worker is not None and self.forensics.worker.isRunning():
            self.forensics.cancel()
            self.forensics.batch_status.setText('Đang hủy an toàn. Hãy đóng lại sau khi ảnh hiện tại hoàn tất.')
            event.ignore()
            return
        if self.stage4.worker is not None and self.stage4.worker.isRunning():
            self.stage4.worker.requestInterruption()
            self.stage4.report_status.setText('Đang hoàn tất/hủy tác vụ nền an toàn. Đóng lại sau khi tác vụ kết thúc.')
            event.ignore()
            return
        super().closeEvent(event)

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Nhập Dataset CSV', '', 'CSV (*.csv)')
        if path:
            try:
                records = load_dataset(path)
                self.records = records
                self.start.clear()
                self.end.clear()
                self.refresh()
            except Exception as error:
                QMessageBox.warning(self, 'Lỗi nhập CSV', str(error))

    def refresh(self):
        super().refresh()
        if hasattr(self, 'timeline_table'):
            self.update_timeline()
        if getattr(self, 'gps_dialog', None) is not None:
            self.refresh_gps_analysis()
        if hasattr(self, 'stage4'):
            self.stage4.refresh()

    def update_timeline(self):
        try:
            self.timeline_rows = build_timeline(self.records, self.start.text(), self.end.text())
        except ValueError as error:
            QMessageBox.warning(self, 'Lỗi Timeline', str(error))
            return
        keys = ['file', 'timestamp', 'source', 'timezone', 'delta_seconds', 'status']
        self.timeline_table.setColumnCount(len(keys))
        self.timeline_table.setHorizontalHeaderLabels(['Ảnh', 'Timestamp', 'Nguồn', 'Múi giờ', 'Chênh lệch (giây)', 'Ghi chú'])
        self.timeline_table.setRowCount(len(self.timeline_rows))
        for i, row in enumerate(self.timeline_rows):
            for j, key in enumerate(keys):
                self.timeline_table.setItem(i, j, QTableWidgetItem(str(row[key])))
        self.timeline_table.resizeColumnsToContents()

    def show_details(self):
        super().show_details()
        if hasattr(self, 'preview'):
            self.preview.clear()
            i = self.table.currentRow()
            if 0 <= i < len(self.records):
                pixmap = QPixmap(self.records[i]['path'])
                if pixmap.isNull():
                    self.preview.setText('Không thể xem ảnh')
                else:
                    self.preview.setPixmap(pixmap.scaled(500, 170, Qt.AspectRatioMode.KeepAspectRatio))

    def save_rows(self, rows, path):
        try:
            export_rows(rows, path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, 'Lỗi xuất CSV', str(error))

    def export_timeline(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất Timeline', 'outputs/timeline.csv', 'CSV (*.csv)')
        if path:
            self.save_rows(self.timeline_rows, path)

    def csv(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất CSV', 'outputs/metadata.csv', 'CSV (*.csv)')
        if path:
            self.save_rows(self.records, path)

    def ml(self):
        """Nút ML cũ chuyển tới mô hình đặc trưng ảnh của Giai đoạn 4."""
        self.workspace_tabs.setCurrentWidget(self.stage4.anomaly_page)
        self.stage4.run_ml()

    def open_gps_analysis(self):
        """Điều tra nguồn GPS, giữ ảnh và metadata gốc ở cửa sổ chính."""
        if self.gps_dialog is None:
            self.gps_dialog = QDialog(self)
            self.gps_dialog.setWindowTitle('GPS Forensics Investigation')
            self.gps_dialog.resize(1180, 800)
            layout = QVBoxLayout(self.gps_dialog)
            note = QLabel('Đối chiếu GPS CSV và EXIF bằng độ tọa độ. Thiếu nguồn không có nghĩa hai nguồn giống nhau. Cảnh báo không chứng minh giả mạo.')
            note.setWordWrap(True)
            layout.addWidget(note)
            controls = QHBoxLayout()
            controls.addWidget(QLabel('Ngưỡng sai lệch GPS (độ tọa độ):'))
            self.gps_tolerance_deg = QDoubleSpinBox()
            self.gps_tolerance_deg.setDecimals(8)
            self.gps_tolerance_deg.setRange(0, 360)
            self.gps_tolerance_deg.setSingleStep(0.0001)
            self.gps_tolerance_deg.setValue(0.0001)
            controls.addWidget(self.gps_tolerance_deg)
            for title, action in [('Cập nhật phân tích', self.refresh_gps_analysis),
                                  ('Xuất đối chiếu CSV', self.export_gps_csv),
                                  ('Xuất điều tra JSON', self.export_gps_json),
                                  ('Xuất bản đồ HTML', self.map_export)]:
                button = QPushButton(title)
                button.clicked.connect(action)
                controls.addWidget(button)
            layout.addLayout(controls)
            self.gps_summary = QLabel('Chưa phân tích.')
            self.gps_summary.setWordWrap(True)
            layout.addWidget(self.gps_summary)
            self.gps_tabs = QTabWidget()
            layout.addWidget(self.gps_tabs)
            self.gps_image_table = QTableWidget()
            self.gps_image_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.gps_tabs.addTab(self.gps_image_table, 'Ảnh và Metadata')
            self.source_table = QTableWidget()
            self.gps_tabs.addTab(self.source_table, 'GPS EXIF / CSV')
            self.alert_table = QTableWidget()
            self.gps_tabs.addTab(self.alert_table, 'Cảnh báo GPS và thời gian')
            self.gps_image_table.itemSelectionChanged.connect(self.select_gps_image)
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                from PySide6.QtWebEngineCore import QWebEngineSettings
                self.map_widget = QWebEngineView()
                self.map_widget.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                self.gps_tabs.addTab(self.map_widget, 'GPS Map')
            except ImportError:
                self.map_widget = None
                self.gps_tabs.addTab(QLabel('Thiếu QtWebEngineWidgets. Vẫn có thể xuất HTML.'), 'GPS Map')
            self.map_status = QLabel('Bản đồ và thư viện Folium cần Internet; CSV màu xanh dương, EXIF xanh lá, nguồn chưa rõ màu xám.')
            self.map_status.setWordWrap(True)
            layout.addWidget(self.map_status)
            if self.map_widget is not None:
                self.map_widget.loadFinished.connect(self.map_load_finished)
        self.refresh_gps_analysis()
        self.gps_dialog.show()
        self.gps_dialog.raise_()

    def select_gps_image(self):
        index = self.gps_image_table.currentRow()
        if 0 <= index < len(self.records):
            self.table.selectRow(index)
            self.show_details()

    def fill_analysis_table(self, table, rows, keys, labels):
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(labels)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, default=str)
                if key in ('csv_status', 'exif_status', 'reference_status', 'status'):
                    labels = {'valid': 'Hợp lệ', 'missing': 'Thiếu dữ liệu', 'invalid': 'Không hợp lệ',
                              'match': 'Khớp trong ngưỡng', 'difference': 'Khác vượt ngưỡng', 'insufficient': 'Chưa đủ dữ liệu'}
                    value = labels.get(value, value)
                item = QTableWidgetItem('' if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()

    def refresh_gps_analysis(self):
        """Mỗi bảng là kết quả mới, không sửa CSV hoặc EXIF gốc."""
        tolerance = validate_tolerance(self.gps_tolerance_deg.value())
        self.gps_analysis = analyze_rules(self.records, gps_tolerance_deg=tolerance)
        self.fill_analysis_table(self.gps_image_table, self.records,
                                 ['file', 'timestamp', 'timestamp_source', 'camera', 'format'],
                                 ['Ảnh', 'Timestamp', 'Nguồn thời gian', 'Camera', 'Định dạng'])
        self.fill_analysis_table(self.source_table, self.gps_analysis['comparisons'],
                                 ['file', 'csv_latitude', 'csv_longitude', 'csv_status', 'exif_latitude', 'exif_longitude',
                                  'exif_status', 'latitude_delta_deg', 'longitude_delta_deg', 'status', 'reason'],
                                 ['Ảnh', 'Vĩ độ CSV', 'Kinh độ CSV', 'CSV', 'Vĩ độ EXIF', 'Kinh độ EXIF',
                                  'EXIF', 'Lệch vĩ độ (độ)', 'Lệch kinh độ (độ)', 'Kết quả', 'Diễn giải'])
        self.fill_analysis_table(self.alert_table, self.gps_analysis['alerts'],
                                 ['file', 'source', 'kind', 'description', 'value', 'level'],
                                 ['Ảnh', 'Nguồn', 'Loại', 'Mô tả', 'Minh chứng', 'Mức'])
        stats = self.gps_analysis['gps_summary']
        self.gps_summary.setText(f'{len(self.records)} ảnh | GPS hợp lệ: {stats["valid"]} | Thiếu mọi nguồn: {stats["missing"]} | Có nguồn sai: {stats["invalid"]}\n'
                                 f'Đối chiếu được: {stats["comparable"]} | Khác vượt ngưỡng: {stats["different"]} | Chưa đủ dữ liệu: {stats["insufficient"]}. Không kết luận thật/giả.')
        path = Path(self.map_directory.name) / 'map.html'
        try:
            export_map(self.records, path)
            if self.map_widget is not None:
                self.map_widget.load(QUrl.fromLocalFile(str(path.resolve())))
        except (OSError, ValueError) as error:
            self.map_status.setText(f'Không tạo được bản đồ: {error}')
        if hasattr(self, 'stage4'):
            self.stage4.refresh()

    def export_gps_csv(self):
        if not self.records:
            QMessageBox.information(self, 'Chưa có dữ liệu', 'Hãy nhập CSV hoặc chọn ảnh trước.')
            return
        self.refresh_gps_analysis()
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất đối chiếu GPS', 'outputs/gps_forensics/comparisons.csv', 'CSV (*.csv)')
        if path:
            try:
                export_rows(self.gps_analysis['comparisons'], protect_output(path, self.records))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Lỗi xuất GPS', str(error))

    def export_gps_json(self):
        if not self.records:
            QMessageBox.information(self, 'Chưa có dữ liệu', 'Hãy nhập CSV hoặc chọn ảnh trước.')
            return
        self.refresh_gps_analysis()
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất điều tra GPS', 'outputs/gps_forensics/investigation.json', 'JSON (*.json)')
        if path:
            try:
                result = dict(gps_tolerance_deg=self.gps_tolerance_deg.value(), **self.gps_analysis)
                protect_output(path, self.records).write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Lỗi xuất GPS', str(error))

    def map_load_finished(self, success):
        self.map_status.setText('HTML đã nạp; bản đồ nền và thư viện cần Internet.' if success
                                else 'Không nạp được HTML. Vẫn có thể xuất HTML để kiểm tra.')

    def map_export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất bản đồ', 'outputs/gps_forensics/map.html', 'HTML (*.html)')
        if path:
            try:
                export_map(self.records, protect_output(path, self.records))
            except (OSError, ValueError) as error:
                QMessageBox.warning(self, 'Lỗi xuất bản đồ', str(error))
