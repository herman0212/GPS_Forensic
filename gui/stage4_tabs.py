"""Giao diện Giai đoạn 4: ML, tổng quan, bản đồ và báo cáo nền."""
from copy import deepcopy
from pathlib import Path
import json
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Qt, QUrl
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
                              QDoubleSpinBox, QTableWidget, QTableWidgetItem,
                              QProgressBar, QFileDialog, QMessageBox, QTabWidget)
from core.machine_learning import run_isolation_forest
from core.stage4_analysis import collect_features, dataset_signature
from core.metadata import export_rows
from core.anomaly import analyze_rules
from core.reporting import build_report, export_pdf, protect_output
from core.map_view import export_map


class Stage4Worker(QThread):
    """ML và PDF chạy trên snapshot, không thao tác widget ở luồng nền."""
    progress = Signal(int, int)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, arguments, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.arguments = deepcopy(arguments)

    def run(self):
        try:
            if self.operation == 'ml':
                records = collect_features(self.arguments['records'], self.progress.emit, self.isInterruptionRequested)
                if self.isInterruptionRequested():
                    raise ValueError('Đã hủy ML.')
                ml = run_isolation_forest(records, self.arguments['contamination'])
                self.result_ready.emit(dict(records=records, ml=ml, signature=self.arguments['signature']))
            else:
                self.result_ready.emit(export_pdf(self.arguments['report'], self.arguments['path']))
        except Exception as error:
            self.failed.emit(f'{type(error).__name__}: {error}')


def score_chart(rows):
    """Histogram điểm ngoại lệ; giá trị càng lớn càng khác biệt thống kê."""
    scores = [r['anomaly_score'] for r in rows if r['anomaly_score'] is not None]
    pixmap = QPixmap(780, 225)
    pixmap.fill(QColor('white'))
    painter = QPainter(pixmap)
    painter.setPen(QColor('black'))
    painter.drawText(15, 22, 'Phân bố anomaly_score = -score_samples (càng lớn càng khác biệt)')
    if scores:
        counts, edges = np.histogram(scores, bins=12)
        peak = max(counts) or 1
        painter.setPen(QColor('#286989'))
        for i, count in enumerate(counts):
            x = 35 + i * 59
            painter.drawRect(x, 180 - int(count * 120 / peak), 45, int(count * 120 / peak))
        painter.setPen(QColor('black'))
        painter.drawText(30, 205, f'{edges[0]:.3f}')
        painter.drawText(710, 205, f'{edges[-1]:.3f}')
        painter.drawText(10, 52, str(peak))
    painter.end()
    return pixmap


class Stage4Tabs(QObject):
    """Bổ sung tab, giữ nguyên các widget và đường xử lý ba giai đoạn trước."""
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker = None
        self.ml_result = None
        self.enriched_records = None
        self.signature = None
        self.overview_page = QWidget()
        self.map_page = QWidget()
        self.anomaly_page = QWidget()
        self.report_page = QWidget()
        self.web_map = None
        self.make_pages()

    def button(self, layout, title, action):
        button = QPushButton(title)
        button.clicked.connect(action)
        layout.addWidget(button)
        return button

    def make_pages(self):
        overview = QVBoxLayout(self.overview_page)
        overview.addWidget(QLabel('GEO IMAGE FORENSICS ANALYZER'))
        self.overview_text = QLabel('Nhập Dataset CSV hoặc chọn thư mục ảnh để bắt đầu.')
        self.overview_text.setWordWrap(True)
        overview.addWidget(self.overview_text)
        self.button(overview, 'Nhập Dataset CSV', self.window.import_csv)
        self.button(overview, 'Chọn thư mục / Batch Processing', self.window.load)
        overview.addStretch()
        self.map_layout = QVBoxLayout(self.map_page)
        self.button(self.map_layout, 'Cập nhật bản đồ', self.update_map)
        self.button(self.map_layout, 'GPS Forensics Investigation / cấu hình đối chiếu', self.window.open_gps_analysis)
        self.map_status = QLabel('Bản đồ cần Internet cho Leaflet và bản đồ nền. Marker tách riêng nguồn CSV và EXIF.')
        self.map_status.setWordWrap(True)
        self.map_layout.addWidget(self.map_status)
        layout = QVBoxLayout(self.anomaly_page)
        self.anomaly_tabs = QTabWidget()
        layout.addWidget(self.anomaly_tabs)
        ml_page = QWidget()
        ml_layout = QVBoxLayout(ml_page)
        controls = QHBoxLayout()
        controls.addWidget(QLabel('contamination:'))
        self.contamination = QDoubleSpinBox()
        self.contamination.setDecimals(3)
        self.contamination.setRange(0.001, 0.5)
        self.contamination.setValue(0.1)
        controls.addWidget(self.contamination)
        self.ml_button = self.button(controls, 'Chạy Isolation Forest', self.run_ml)
        self.csv_button = self.button(controls, 'Xuất ML CSV', self.export_ml)
        ml_layout.addLayout(controls)
        self.progress = QProgressBar()
        ml_layout.addWidget(self.progress)
        self.ml_status = QLabel('Chưa chạy ML. Đặc trưng ảnh: dung lượng, chiều rộng, chiều cao, JPEG MAE. Chỉ dùng đặc trưng ảnh, không dùng GPS/thời gian.')
        self.ml_status.setWordWrap(True)
        ml_layout.addWidget(self.ml_status)
        self.ml_table = QTableWidget()
        ml_layout.addWidget(self.ml_table)
        self.chart = QLabel('Chưa có phân bố điểm.')
        ml_layout.addWidget(self.chart)
        self.anomaly_tabs.addTab(ml_page, 'Machine Learning / Phát hiện ngoại lệ')
        rules = QWidget()
        rule_layout = QVBoxLayout(rules)
        self.button(rule_layout, 'GPS Forensics / cấu hình luật', self.window.open_gps_analysis)
        self.rule_table = QTableWidget()
        rule_layout.addWidget(self.rule_table)
        self.anomaly_tabs.addTab(rules, 'Cảnh báo theo quy tắc')
        report = QVBoxLayout(self.report_page)
        self.report_status = QLabel('Xuất báo cáo chỉ từ kết quả đã phân tích. ML chưa chạy sẽ được ghi rõ.')
        self.report_status.setWordWrap(True)
        report.addWidget(self.report_status)
        self.report_progress = QProgressBar()
        report.addWidget(self.report_progress)
        self.pdf_button = self.button(report, 'Xuất PDF tiếng Việt', self.choose_pdf)
        self.json_button = self.button(report, 'Xuất snapshot báo cáo JSON', self.export_json)
        report.addStretch()

    def rule_options(self):
        w = self.window
        if w.gps_dialog is None:
            return {}
        return dict(gps_tolerance_deg=w.gps_tolerance_deg.value())

    def refresh(self):
        current = dataset_signature(self.window.records)
        if self.signature is not None and current != self.signature:
            self.ml_result = self.enriched_records = self.signature = None
            self.ml_table.setRowCount(0)
            self.chart.setText('Bộ dữ liệu đã thay đổi; cần chạy lại ML.')
            self.ml_status.setText('Kết quả ML cũ đã bỏ khỏi phiên hiện tại vì bộ dữ liệu thay đổi.')
        report = build_report(self.window.records, rule_options=self.rule_options())
        self.overview_text.setText(f'Tổng {report["total"]} ảnh | CSV: {report["metadata"]["csv"]} | EXIF: {report["metadata"]["exif_present"]}\n'
                                  f'GPS hợp lệ: {report["gps"]["valid"]} | Timestamp hợp lệ: {report["timeline"]["valid"]} | Chưa rõ múi giờ: {report["timeline"]["unknown_timezone"]}\n'
                                  'Bất thường metadata, ngoại lệ thống kê và giả mạo là ba khái niệm khác nhau.')
        self.fill_table(self.rule_table, report['alerts'], ['file', 'source', 'kind', 'description', 'value', 'level'])
        if self.web_map is not None:
            self.update_map()

    def fill_table(self, table, rows, keys):
        table.setColumnCount(len(keys))
        labels = {'file': 'Ảnh', 'source': 'Nguồn', 'label': 'Nhãn', 'imputed_features': 'Đặc trưng điền trung vị',
                  'reason': 'Lý do', 'kind': 'Loại', 'description': 'Mô tả', 'value': 'Giá trị',
                  'level': 'Mức', 'file_bytes': 'Dung lượng byte', 'width': 'Chiều rộng', 'height': 'Chiều cao'}
        table.setHorizontalHeaderLabels([labels.get(key, key) for key in keys])
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                value = row.get(key)
                item = QTableWidgetItem('' if value is None else str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        table.resizeColumnsToContents()

    def run_ml(self):
        if not self.window.records:
            self.ml_status.setText('Chưa có ảnh. Hãy nhập CSV hoặc kết quả Batch.')
            return
        current = dataset_signature(self.window.records)
        records = self.enriched_records if self.signature == current and self.enriched_records is not None else self.window.records
        self.start_worker('ml', dict(records=records, contamination=self.contamination.value(), signature=current))

    def start_worker(self, operation, arguments):
        if self.worker is not None and self.worker.isRunning():
            self.ml_status.setText('Đang có tác vụ ML/PDF; hãy chờ hoàn tất.')
            return False
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker = Stage4Worker(operation, arguments, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.result_ready.connect(self.on_result)
        self.worker.failed.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.set_busy(True)
        self.progress.setRange(0, 0)
        if operation == 'ml':
            self.ml_status.setText('Đang chuẩn bị đặc trưng và chạy ML trên luồng nền…')
        else:
            self.report_status.setText('Đang tạo PDF trên luồng nền…')
        self.worker.start()
        return True

    def set_busy(self, busy):
        for button in (self.ml_button, self.pdf_button, self.csv_button, self.json_button):
            button.setEnabled(not busy)
        self.report_progress.setRange(0, 0 if busy else 1)
        self.report_progress.setValue(0 if busy else 1)

    def on_progress(self, done, total):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.ml_status.setText(f'Chuẩn bị đặc trưng: {done}/{total}; sau đó huấn luyện Isolation Forest.')

    def on_result(self, result):
        if self.worker.operation == 'pdf':
            self.report_status.setText('Đã xuất PDF: ' + result)
            return
        if result['signature'] != dataset_signature(self.window.records):
            self.ml_status.setText('Bộ ảnh đã đổi trong khi chạy; bỏ kết quả ML để tránh dùng nhầm.')
            return
        self.signature = result['signature']
        self.enriched_records = result['records']
        self.ml_result = result['ml']
        ml = self.ml_result
        self.fill_table(self.ml_table, ml['results'], ['file', 'label', 'anomaly_score', 'decision_function', 'imputed_features', 'reason'] + ml['features'])
        self.chart.setPixmap(score_chart(ml['results']))
        self.ml_status.setText(f'Normal: {ml["normal"]} | Anomaly: {ml["anomaly"]} | Loại: {ml["excluded"]}\n'
                               f'Đặc trưng: {", ".join(ml["features"])}. {ml["score_description"]}')

    def on_error(self, message):
        self.ml_status.setText(message)
        self.report_status.setText(message)

    def on_finished(self):
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.set_busy(False)

    def snapshot(self):
        self.refresh()
        records = self.enriched_records if self.enriched_records is not None else self.window.records
        return build_report(records, self.ml_result, 'Bộ ảnh trong phiên GeoImageForensics', self.rule_options())

    def choose_pdf(self):
        if not self.window.records:
            self.report_status.setText('Chưa có dữ liệu để báo cáo.')
            return
        path, _ = QFileDialog.getSaveFileName(self.window, 'Xuất PDF', 'outputs/gps_forensics/report.pdf', 'PDF (*.pdf)')
        if path:
            self.start_worker('pdf', dict(report=self.snapshot(), path=path))

    def export_ml(self):
        self.refresh()
        if self.ml_result is None:
            self.ml_status.setText('Hãy chạy ML trước khi xuất CSV.')
            return
        path, _ = QFileDialog.getSaveFileName(self.window, 'Xuất ML', 'outputs/gps_forensics/ml_results.csv', 'CSV (*.csv)')
        if path:
            try:
                export_rows(self.ml_result['results'], protect_output(path, self.window.records))
            except (OSError, ValueError) as error:
                self.ml_status.setText(str(error))

    def export_json(self):
        if not self.window.records:
            self.report_status.setText('Chưa có dữ liệu để báo cáo.')
            return
        path, _ = QFileDialog.getSaveFileName(self.window, 'Xuất snapshot', 'outputs/gps_forensics/report_snapshot.json', 'JSON (*.json)')
        if path:
            try:
                target = protect_output(path, self.window.records)
                target.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
            except (OSError, ValueError) as error:
                self.report_status.setText(str(error))

    def update_map(self):
        if self.web_map is None:
            try:
                from PySide6.QtWebEngineWidgets import QWebEngineView
                from PySide6.QtWebEngineCore import QWebEngineSettings
                self.web_map = QWebEngineView()
                self.web_map.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
                self.map_layout.addWidget(self.web_map)
                self.web_map.loadFinished.connect(self.on_map_loaded)
            except ImportError:
                self.map_status.setText('Thiếu QtWebEngineWidgets. Có thể dùng chức năng xuất bản đồ HTML.')
                return
        path = Path(self.window.map_directory.name) / 'stage4_map.html'
        try:
            export_map(self.window.records, path)
            self.web_map.load(QUrl.fromLocalFile(str(path.resolve())))
        except (OSError, ValueError) as error:
            self.map_status.setText(f'Không tạo được bản đồ: {error}')

    def on_map_loaded(self, success):
        self.map_status.setText('HTML đã nạp; nguồn CSV xanh dương, EXIF xanh lá. Bản đồ nền cần Internet.' if success
                                else 'Không nạp được bản đồ. Có thể xuất HTML để kiểm tra; không bỏ qua lỗi mạng.')
