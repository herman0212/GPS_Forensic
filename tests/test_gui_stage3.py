"""Kiểm thử QThread và cập nhật widget thật ở chế độ offscreen."""
from PIL import Image
from core.integrity import sha256_file


def test_gui_batch_jpeg_comparison_and_cancellation(tmp_path, monkeypatch):
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QEventLoop, QTimer
    from gui.main_window import Window
    app = QApplication.instance() or QApplication([])
    window = Window()
    panel = window.forensics
    a, b = tmp_path / 'a.jpg', tmp_path / 'b.jpg'
    Image.new('RGB', (40, 30), 'red').save(a)
    Image.new('RGB', (40, 30), 'blue').save(b)
    baseline = {p: sha256_file(p) for p in (a, b)}

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
        assert not panel.worker.isRunning(), 'QThread chưa kết thúc trong 15 giây'
        timer.stop()

    try:
        assert window.workspace_tabs.tabText(1) == 'Batch Processing'
        assert window.workspace_tabs.tabText(2) == 'JPEG Analysis'
        panel.folder.setText(str(tmp_path))
        panel.start_batch()
        wait_finished()
        assert len(panel.rows) == panel.batch_table.rowCount() == 2
        assert all(r['success'] and r['hash_unchanged'] for r in panel.rows)
        panel.use_results()
        assert window.table.rowCount() == window.timeline_table.rowCount() == 2
        assert panel.start_worker('jpeg', (str(a), 90))
        wait_finished()
        assert not panel.original_preview.pixmap().isNull()
        assert not panel.difference_preview.pixmap().isNull()
        assert not panel.histogram.pixmap().isNull()
        assert 'jpeg_structure' in panel.jpeg_details.toPlainText()
        assert panel.start_worker('compare', [str(a), str(b)])
        wait_finished()
        assert 'pixel_mae' in panel.jpeg_details.toPlainText()
        panel.recheck()
        wait_finished()
        assert all(r['hash_unchanged'] for r in panel.rows)
        panel.start_batch()
        panel.cancel()
        wait_finished()
        assert all(sha256_file(p) == h for p, h in baseline.items())
        assert panel.start_button.isEnabled()
    finally:
        if panel.worker is not None and panel.worker.isRunning():
            panel.cancel()
            panel.worker.wait(15000)
        window.close()
        window.map_directory.cleanup()
        app.processEvents()
