"""GUI GPS Forensics: đối chiếu nguồn, xuất kết quả và xem ảnh."""
import json
from pathlib import Path


def test_gui_gps_forensics_and_exports(monkeypatch,tmp_path):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication,QFileDialog
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from gui.main_window import Window
    from core.metadata import load_dataset
    urls=[]
    monkeypatch.setattr(QWebEngineView,'load',lambda self,url:urls.append(url))
    app=QApplication.instance() or QApplication([])
    window=Window()
    try:
        window.records=load_dataset('data/Image2GPS25/metadata.csv')
        window.refresh()
        window.open_gps_analysis()
        assert window.gps_dialog.windowTitle()=='GPS Forensics Investigation'
        assert isinstance(window.map_widget,QWebEngineView)
        assert urls[-1].isLocalFile() and Path(urls[-1].toLocalFile()).is_file()
        assert window.table.rowCount()==window.timeline_table.rowCount()==100
        assert window.source_table.rowCount()==window.gps_image_table.rowCount()==100
        assert all(r['status']=='insufficient' for r in window.gps_analysis['comparisons'])
        for name in ('journey_table','journey_name','pairs_table','shared_clock','distance_limit','speed_limit'):
            assert not hasattr(window,name)
        window.gps_tolerance_deg.setValue(0.001)
        window.refresh_gps_analysis()
        assert window.stage4.rule_options()=={'gps_tolerance_deg':0.001}
        window.gps_image_table.selectRow(0)
        assert window.table.currentRow()==0
        assert not window.preview.pixmap().isNull()
        target=tmp_path/'gps.json'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
        window.export_gps_json()
        result=json.loads(target.read_text(encoding='utf-8'))
        assert result['gps_tolerance_deg']==0.001
        assert result['gps_summary']['csv_valid']==100
        target=tmp_path/'gps.csv'
        window.export_gps_csv()
        assert 'latitude_delta_deg' in target.read_text(encoding='utf-8-sig')
        target=tmp_path/'gps.html'
        window.map_export()
        assert target.is_file()
    finally:
        if window.gps_dialog:
            window.gps_dialog.close()
        window.close()
        window.map_directory.cleanup()
        app.processEvents()


def test_gui_without_webengine_still_exports(monkeypatch,tmp_path):
    monkeypatch.setenv('QT_QPA_PLATFORM','offscreen')
    import builtins
    from PySide6.QtWidgets import QApplication,QFileDialog
    from gui.main_window import Window
    original_import=builtins.__import__
    def unavailable(name,*args,**kwargs):
        if name=='PySide6.QtWebEngineWidgets':
            raise ImportError('WebEngine không có trong ca thử')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',unavailable)
    app=QApplication.instance() or QApplication([])
    window=Window()
    try:
        window.records=[dict(file='a.jpg',timestamp='',latitude=10,longitude=106,exif={'latitude':10,'longitude':106})]
        window.open_gps_analysis()
        assert window.map_widget is None
        target=tmp_path/'fallback.html'
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),''))
        window.map_export()
        assert target.is_file()
    finally:
        window.gps_dialog.close()
        window.close()
        window.map_directory.cleanup()
        app.processEvents()
