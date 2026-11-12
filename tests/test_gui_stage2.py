"""Kiểm tra tích hợp GUI không tải bản đồ nền qua Internet."""
from pathlib import Path


def test_gui_group_speed_and_stage1(monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QItemSelectionModel
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from gui.main_window import Window
    from core.metadata import load_dataset
    loaded_urls = []
    # Vẫn tạo QtWebEngine thật nhưng chặn tải mạng trong bài kiểm thử.
    monkeypatch.setattr(QWebEngineView, 'load', lambda self, url: loaded_urls.append(url))
    app = QApplication.instance() or QApplication([])
    window = Window()
    try:
        window.records = load_dataset('data/Image2GPS25/metadata.csv')
        window.refresh()
        window.open_gps_analysis()
        assert isinstance(window.map_widget, QWebEngineView)
        assert loaded_urls[-1].isLocalFile()
        assert Path(loaded_urls[-1].toLocalFile()).is_file()
        assert window.table.rowCount() == window.timeline_table.rowCount() == 100
        assert window.pairs_table.rowCount() == 0
        flags = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
        selection = window.journey_table.selectionModel()
        for row in (0, 1):
            selection.select(window.journey_table.model().index(row, 0), flags)
        window.journey_name.setText('Nhóm kiểm thử đã xác nhận')
        window.assign_journey()
        assert window.pairs_table.rowCount() == 1
        assert window.pairs_table.item(0, 5).text() == ''
        window.shared_clock.setChecked(True)
        window.refresh_gps_analysis()
        assert float(window.pairs_table.item(0, 5).text()) >= 0
        assert window.records[0]['csv_original']['timestamp'] == '2025-11-22T14:43:19'
    finally:
        if window.gps_dialog:
            window.gps_dialog.close()
        window.close()
        window.map_directory.cleanup()
        app.processEvents()
