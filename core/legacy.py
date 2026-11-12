"""Geo Image Forensics Analyzer — educational prototype.
Run: pip install -r requirements.txt && python main.py
Optional: install ExifTool and add it to PATH for robust EXIF/GPS parsing.
"""
import csv
import hashlib
import io
import json
import math
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PIL import Image, ExifTags
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QHeaderView, QTextEdit)

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp'}

def digest(path):
    from core.integrity import sha256_file
    return sha256_file(path)


def parse_time(value):
    if not value:
        return None
    from core.timeline import parse_time as parse_timestamp
    return parse_timestamp(value)

def rational(x):
    try:
        return float(x)
    except (ValueError, TypeError, ZeroDivisionError):
        return None

def gps_decimal(dms, ref):
    try:
        v = [rational(x) for x in dms]
        if any(x is None for x in v):
            return None
        n = v[0] + v[1]/60 + v[2]/3600
        return -n if str(ref).upper() in ('S', 'W') else n
    except (ValueError, TypeError, IndexError):
        return None

def exiftool_data(path):
    if not shutil.which('exiftool'):
        return {}
    try:
        proc = subprocess.run(['exiftool', '-json', '-n', '-G1', str(path)],
                              capture_output=True, text=True, timeout=25, check=True)
        return json.loads(proc.stdout)[0]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return {}

def get_first(d, keys):
    for k in keys:
        if k in d and d[k] not in ('', None):
            return d[k]
    return None

def inspect_image(path):
    from core.batch import analyze_file
    record = analyze_file(path)
    record['sha256'] = record['sha256_before']
    return record


def analyze(records):
    counts = Counter(r['timestamp'] for r in records if parse_time(r['timestamp']))
    for r in records:
        if r['timestamp'] and counts[r['timestamp']] > 1:
            r['warnings'].append('Timestamp trùng')
    return records

def export_map(records, output):
    import folium
    valid = [r for r in records if r['latitude'] is not None and r['longitude'] is not None]
    if not valid:
        raise ValueError('Không có ảnh chứa tọa độ GPS hợp lệ')
    center = [sum(r['latitude'] for r in valid)/len(valid),
              sum(r['longitude'] for r in valid)/len(valid)]
    m = folium.Map(location=center, zoom_start=10)
    for r in valid:
        label = f"{r['file']} | {r['timestamp'] or 'Không rõ thời gian'}"
        folium.Marker([r['latitude'], r['longitude']], tooltip=label).add_to(m)
    m.save(str(output))

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.records = []
        self.setWindowTitle('Geo Image Forensics Analyzer')
        self.resize(1200, 740)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        bar = QHBoxLayout()
        for label, action in [('Chọn thư mục ảnh', self.load), ('Xuất CSV', self.csv),
                              ('Xuất JSON', self.json_export), ('Xuất bản đồ HTML', self.map_export),
                              ('ML: phát hiện bất thường', self.ml)]:
            btn = QPushButton(label)
            btn.clicked.connect(action)
            bar.addWidget(btn)
        layout.addLayout(bar)
        self.summary = QLabel('Chọn thư mục để bắt đầu phân tích.')
        layout.addWidget(self.summary)
        columns = ['Tên ảnh', 'Timestamp', 'Múi giờ', 'Vĩ độ', 'Kinh độ',
                   'Camera', 'Định dạng', 'JPEG MAE', 'Cảnh báo']
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(155)
        layout.addWidget(self.details)
        self.table.itemSelectionChanged.connect(self.show_details)

    def load(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh')
        if not folder:
            return
        files = sorted(p for p in Path(folder).rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.records = analyze([inspect_image(p) for p in files])
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh()

    def refresh(self):
        self.table.setRowCount(len(self.records))
        for i, r in enumerate(self.records):
            values = [r['file'], r['timestamp'], r['offset'],
                      '' if r['latitude'] is None else f"{r['latitude']:.6f}",
                      '' if r['longitude'] is None else f"{r['longitude']:.6f}",
                      r['camera'], r['format'], str(r['jpeg_recompress_mae'] or ''),
                      '; '.join(r['warnings'])]
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(str(v)))
        gps = sum(r['latitude'] is not None for r in self.records)
        self.summary.setText(f'Đã phân tích: {len(self.records)} ảnh | Có GPS: {gps} | '
                             f'Có timestamp: {sum(bool(parse_time(r["timestamp"])) for r in self.records)}')

    def show_details(self):
        i = self.table.currentRow()
        if 0 <= i < len(self.records):
            self.details.setPlainText(json.dumps(self.records[i], indent=2, ensure_ascii=False))

    def csv(self):
        if not self.records:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất CSV', 'timeline.csv', 'CSV (*.csv)')
        if path:
            with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.records[0].keys())
                writer.writeheader()
                for r in self.records:
                    writer.writerow({k: '; '.join(v) if isinstance(v, list) else v for k,v in r.items()})

    def json_export(self):
        if not self.records:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất JSON', 'report.json', 'JSON (*.json)')
        if path:
            Path(path).write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding='utf-8')

    def map_export(self):
        if not self.records:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Xuất bản đồ', 'map.html', 'HTML (*.html)')
        if path:
            try:
                export_map(self.records, path)
                QMessageBox.information(self, 'Thành công', f'Đã lưu bản đồ tại:\n{path}')
            except Exception as e:
                QMessageBox.warning(self, 'Lỗi', str(e))

    def ml(self):
        from sklearn.ensemble import IsolationForest
        import numpy as np
        valid = [r for r in self.records if r['latitude'] is not None and
                 r['longitude'] is not None and parse_time(r['timestamp'])]
        if len(valid) < 10:
            QMessageBox.information(self, 'Chưa đủ dữ liệu', 'Cần ít nhất 10 ảnh có GPS và timestamp.')
            return
        # Exploratory outlier detection, not evidence of manipulation.
        t0 = min(parse_time(r['timestamp']) for r in valid)
        X = np.array([[r['latitude'], r['longitude'],
                       (parse_time(r['timestamp'])-t0).total_seconds()/3600] for r in valid])
        from sklearn.preprocessing import StandardScaler
        X = StandardScaler().fit_transform(X)
        pred = IsolationForest(n_estimators=100, contamination=.1, random_state=42).fit_predict(X)
        for r, p in zip(valid, pred):
            if p == -1 and 'ML: điểm ngoại lệ (cần kiểm tra)' not in r['warnings']:
                r['warnings'].append('ML: điểm ngoại lệ (cần kiểm tra)')
        self.refresh()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Window()
    w.show()
    sys.exit(app.exec())


