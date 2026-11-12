"""Giao diện Giai đoạn 1 mở rộng cửa sổ thử nghiệm hiện có."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap, QFont, QFontDatabase
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QPushButton, QLabel, QLineEdit,
                              QTableWidget, QTableWidgetItem, QDialog, QVBoxLayout,
                              QHBoxLayout, QTabWidget, QDoubleSpinBox, QCheckBox, QWidget, QApplication)
from pathlib import Path
from tempfile import TemporaryDirectory
from core.legacy import Window as LegacyWindow
from core.metadata import load_dataset, export_rows
from core.timeline import build_timeline
from core.gps import compare_positions
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
        button = QPushButton('GPS / Khoảng cách / Bản đồ / Cảnh báo')
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
        """Mở bảng chọn nhóm hành trình, ngưỡng cảnh báo và bản đồ nhúng."""
        if self.gps_dialog is None:
            self.gps_dialog = QDialog(self)
            self.gps_dialog.setWindowTitle('Phân tích GPS và thời gian — Giai đoạn 2')
            self.gps_dialog.resize(1150, 800)
            layout = QVBoxLayout(self.gps_dialog)
            note = QLabel('Chỉ gán cùng nhóm khi đã xác nhận cùng hành trình. Cảnh báo không kết luận ảnh giả mạo.')
            note.setWordWrap(True)
            layout.addWidget(note)
            controls = QHBoxLayout()
            self.journey_name = QLineEdit()
            self.journey_name.setPlaceholderText('Tên nhóm hành trình đã xác nhận')
            controls.addWidget(self.journey_name)
            for text, action in [('Gán nhóm cho ảnh chọn', self.assign_journey),
                                 ('Bỏ nhóm ảnh chọn', self.clear_journey),
                                 ('So sánh 2 ảnh chọn', self.compare_selected)]:
                button = QPushButton(text)
                button.clicked.connect(action)
                controls.addWidget(button)
            layout.addLayout(controls)
            self.shared_clock = QCheckBox('Tôi xác nhận giờ không offset trong các nhóm dùng cùng cơ sở đồng hồ')
            layout.addWidget(self.shared_clock)
            thresholds = QHBoxLayout()
            self.distance_limit = self.threshold(thresholds, 'Khoảng cách (km)', 500)
            self.speed_limit = self.threshold(thresholds, 'Vận tốc (km/h)', 900)
            self.gps_difference = self.threshold(thresholds, 'Sai khác CSV/EXIF (km)', 0.1)
            button = QPushButton('Phân tích lại / cập nhật bản đồ')
            button.clicked.connect(self.refresh_gps_analysis)
            thresholds.addWidget(button)
            layout.addLayout(thresholds)
            self.comparison = QLabel('Chọn đúng 2 dòng trong tab Ảnh để so sánh.')
            self.comparison.setWordWrap(True)
            layout.addWidget(self.comparison)
            self.gps_tabs = QTabWidget()
            layout.addWidget(self.gps_tabs)
            self.journey_table = QTableWidget()
            self.journey_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.journey_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
            self.gps_tabs.addTab(self.journey_table, 'Ảnh / Nhóm xác nhận')
            self.pairs_table = QTableWidget()
            self.gps_tabs.addTab(self.pairs_table, 'Khoảng cách / Vận tốc')
            self.alert_table = QTableWidget()
            self.gps_tabs.addTab(self.alert_table, 'Cảnh báo')
            # QWebEngineView là thành phần của PySide6, chỉ nạp khi mở bản đồ.
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                from PySide6.QtWebEngineCore import QWebEngineSettings
                self.map_widget = QWebEngineView()
                self.map_widget.settings().setAttribute(
                    QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                self.gps_tabs.addTab(self.map_widget, 'GPS Map')
            except ImportError:
                self.map_widget = None
                self.gps_tabs.addTab(QLabel('Thiếu QtWebEngineWidgets. Cài PySide6 đầy đủ; vẫn có thể xuất HTML.'), 'GPS Map')
            self.map_status = QLabel('Bản đồ nền và thư viện Folium cần kết nối Internet.')
            layout.addWidget(self.map_status)
            if self.map_widget is not None:
                self.map_widget.loadFinished.connect(self.map_load_finished)
            self.refresh_gps_analysis()
        self.gps_dialog.show()
        self.gps_dialog.raise_()

    def threshold(self, layout, label, value):
        """Tạo ô ngưỡng dương để tránh tham số không có ý nghĩa."""
        layout.addWidget(QLabel(label))
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(0.001, 1000000)
        spin.setValue(value)
        layout.addWidget(spin)
        return spin

    def selected_gps_rows(self):
        return sorted({item.row() for item in self.journey_table.selectedItems()})

    def assign_journey(self):
        name = self.journey_name.text().strip()
        rows = self.selected_gps_rows()
        if not name or not rows:
            QMessageBox.information(self, 'Chọn nhóm', 'Nhập tên nhóm và chọn các dòng ảnh đã xác nhận cùng hành trình.')
            return
        for index in rows:
            self.records[index]['journey_group'] = name
        self.refresh_gps_analysis()

    def clear_journey(self):
        for index in self.selected_gps_rows():
            self.records[index].pop('journey_group', None)
        self.refresh_gps_analysis()

    def compare_selected(self):
        rows = self.selected_gps_rows()
        if len(rows) != 2:
            self.comparison.setText('Cần chọn đúng 2 ảnh (giữ Ctrl để chọn nhiều dòng).')
            return
        first, second = [self.records[i] for i in rows]
        from core.timeline import parse_time
        a, b = parse_time(first.get('timestamp')), parse_time(second.get('timestamp'))
        if a and b and (a.tzinfo is None) == (b.tzinfo is None) and a > b:
            first, second = second, first
        result = compare_positions(first, second, self.shared_clock.isChecked())
        distance = 'không tính' if result['distance_km'] is None else f'{result["distance_km"]:.3f} km'
        speed = 'không tính' if result['speed_kmh'] is None else f'{result["speed_kmh"]:.3f} km/h'
        self.comparison.setText(f'{first["file"]} → {second["file"]}: {distance}; vận tốc: {speed}. {result["reason"]}')

    def fill_analysis_table(self, table, rows, keys, labels):
        table.setColumnCount(len(keys))
        table.setHorizontalHeaderLabels(labels)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                value = row.get(key)
                item = QTableWidgetItem('' if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()

    def refresh_gps_analysis(self):
        """Chỉ xuất kết quả suy luận riêng, không sửa CSV/EXIF gốc."""
        alerts, pairs = analyze_rules(self.records, self.distance_limit.value(), self.speed_limit.value(),
                                     self.gps_difference.value(), self.shared_clock.isChecked())
        self.fill_analysis_table(self.journey_table, self.records,
                                 ['file', 'timestamp', 'latitude', 'longitude', 'journey_group'],
                                 ['Ảnh', 'Timestamp', 'Vĩ độ', 'Kinh độ', 'Nhóm do người dùng xác nhận'])
        self.fill_analysis_table(self.pairs_table, pairs,
                                 ['first', 'second', 'group', 'distance_km', 'delta_seconds', 'speed_kmh', 'reason'],
                                 ['Ảnh trước', 'Ảnh sau', 'Nhóm', 'Khoảng cách km', 'Giây', 'km/h', 'Lý do không tính'])
        self.fill_analysis_table(self.alert_table, alerts, ['file', 'kind', 'description', 'value', 'level'],
                                 ['Ảnh', 'Loại', 'Mô tả', 'Giá trị', 'Mức cảnh báo'])
        self.comparison.setText(f'{len(alerts)} cảnh báo/thông tin; {len(pairs)} cặp trong nhóm xác nhận. Không kết luận giả mạo.')
        path = Path(self.map_directory.name) / 'map.html'
        try:
            export_map(self.records, path)
            if self.map_widget is not None:
                self.map_widget.load(QUrl.fromLocalFile(str(path.resolve())))
        except OSError as error:
            self.map_status.setText(f'Không tạo được bản đồ: {error}')

    def map_load_finished(self, success):
        self.map_status.setText('HTML đã nạp; bản đồ nền và thư viện cần Internet.' if success
                                else 'Không nạp được HTML bản đồ. Có thể dùng nút xuất HTML để thử lại.')

    def map_export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất bản đồ', 'outputs/map.html', 'HTML (*.html)')
        if path:
            try:
                export_map(self.records, path)
            except OSError as error:
                QMessageBox.warning(self, 'Lỗi xuất bản đồ', str(error))
