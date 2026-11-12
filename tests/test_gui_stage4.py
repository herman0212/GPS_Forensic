"""Kiểm tra worker ML/PDF, bộ tab và loại bỏ kết quả lỗi thời."""
from PIL import Image
from core.batch import analyze_file
from core.integrity import sha256_file


def test_gui_ml_pdf_and_invalidation(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop, QTimer
    from gui.main_window import Window
    app = QApplication.instance() or QApplication([])
    window = Window()
    from PySide6.QtGui import QFontMetrics
    assert QFontMetrics(app.font()).inFontUcs4(ord('ệ'))
    panel = window.stage4
    paths = []
    for i in range(8):
        path = tmp_path / f'{i}.jpg'
        Image.new('RGB', (30 + i, 20 + i), (i * 25, 20, 80)).save(path)
        paths.append(path)
    baseline = {p: sha256_file(p) for p in paths}

    def wait_finished():
        loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        panel.worker.finished.connect(loop.quit)
        timer.start(15000)
        if panel.worker.isRunning():
            loop.exec()
        app.processEvents()
        assert not panel.worker.isRunning()
        timer.stop()

    try:
        assert window.workspace_tabs.count() == 8
        assert window.workspace_tabs.currentWidget() is panel.overview_page
        window.records = [analyze_file(p) for p in paths]
        window.refresh()
        panel.contamination.setValue(0.25)
        panel.run_ml()
        wait_finished()
        assert panel.ml_result is not None
        assert panel.ml_table.rowCount() == 8
        assert panel.ml_result['anomaly'] + panel.ml_result['normal'] == 8
        assert not panel.chart.pixmap().isNull()
        path = tmp_path / 'gui.pdf'
        panel.start_worker('pdf', dict(report=panel.snapshot(), path=str(path)))
        wait_finished()
        assert path.is_file()
        assert 'Đã xuất PDF' in panel.report_status.text()
        window.records[0]['timestamp'] = 'changed'
        window.refresh()
        assert panel.ml_result is None
        assert panel.ml_table.rowCount() == 0
        assert all(sha256_file(p) == value for p, value in baseline.items())
    finally:
        if panel.worker is not None and panel.worker.isRunning():
            panel.worker.requestInterruption()
            panel.worker.wait(15000)
        window.close()
        window.map_directory.cleanup()
        app.processEvents()
