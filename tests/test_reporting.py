"""PDF Unicode, nguồn dữ liệu và bảo vệ đầu ra."""
import pytest
from pypdf import PdfReader
from core.reporting import build_report, export_pdf, protect_output
from core.machine_learning import run_isolation_forest
from core.stage4_analysis import collect_features
from core.integrity import sha256_file
from tests.test_machine_learning import sample_records


def test_unanalyzed_data_not_fabricated():
    report = build_report([dict(file='ảnh.jpg', timestamp='', latitude=None, longitude=None)])
    assert report['ml'] is None
    assert report['jpeg']['mean_mae'] is None
    assert report['integrity']['measured'] == 0
    assert report['integrity']['not_measured'] == 1


def test_pdf_unicode_and_content(tmp_path):
    records = sample_records()
    ml = run_isolation_forest(records)
    report = build_report(records, ml, 'Thử nghiệm tiếng Việt: ảnh số, dữ liệu gốc')
    path = tmp_path / 'report.pdf'
    export_pdf(report, path)
    reader = PdfReader(path)
    text = ' '.join(' '.join(p.extract_text() for p in reader.pages).split())
    assert len(reader.pages) >= 4
    assert 'Thử nghiệm tiếng Việt' in text
    assert 'không đủ để kết luận giả mạo' in text
    assert 'Isolation Forest' in text and 'anomaly_score' in text
    assert 'Chưa có đủ hai hash' in text
    fonts = [font.get_object() for page in reader.pages for font in page['/Resources']['/Font'].get_object().values()]
    assert any('/ToUnicode' in font for font in fonts)


def test_pdf_without_ml(tmp_path):
    report = build_report([dict(file='a.jpg', timestamp='')])
    path = tmp_path / 'no_ml.pdf'
    export_pdf(report, path)
    assert 'Chưa chạy Machine Learning' in '\n'.join(p.extract_text() for p in PdfReader(path).pages)


def test_report_rejects_unrelated_ml():
    records = sample_records()
    ml = run_isolation_forest(records)
    records[0]['file'] = 'other.jpg'
    with pytest.raises(ValueError):
        build_report(records, ml)


def test_protected_output_paths():
    for path in ['data/Image2GPS25/metadata.csv', 'outputs/chapter3_evidence/report.pdf', 'outputs/stage3_validation.json']:
        with pytest.raises(ValueError):
            protect_output(path)


def test_collect_features_preserves_csv_and_source_hash(tmp_path):
    from PIL import Image
    path = tmp_path / 'test.jpg'
    Image.new('RGB', (30, 20), 'red').save(path)
    before = sha256_file(path)
    original = dict(file=path.name, path=str(path), timestamp='2025-01-01T00:00:00', latitude=10,
                    longitude=106, csv_original={'lat': '10'}, timestamp_source='CSV')
    result = collect_features([original])[0]
    assert result['timestamp_source'] == 'CSV' and result['latitude'] == 10
    assert result['width'] == 30 and result['hash_unchanged']
    assert result['exif']['timestamp'] == ''
    assert 'width' not in original
    assert sha256_file(path) == before


def test_gps_forensics_report_json_and_pdf(tmp_path):
    import json
    rows = [dict(file='a.jpg',timestamp='2025-01-01T00:00:00',
                 csv_original={'lat':'10','lon':'106'},exif={'latitude':10.001,'longitude':106}),
            dict(file='b.jpg',timestamp='',exif={'latitude':0,'longitude':0}),
            dict(file='c.jpg',timestamp='bad',csv_original={'lat':'91','lon':'0'},exif={}),
            dict(file='d.jpg',timestamp='',exif={})]
    report = build_report(rows,rule_options={'gps_tolerance_deg':0.0001})
    assert report['gps']['valid'] == 2
    assert report['gps']['missing'] == report['gps']['invalid'] == 1
    assert report['gps']['csv_present'] == report['gps']['exif_present'] == 2
    assert report['gps']['comparable'] == report['gps']['different'] == 1
    text = json.dumps(report,ensure_ascii=False)
    for removed in ('distance_limit','speed_limit','shared_clock','distance_km','speed_kmh','journey_group'):
        assert removed not in text
    assert 'gps_tolerance_deg' in text and 'gps_comparisons' in text
    path = tmp_path/'gps.pdf'
    export_pdf(report,path)
    content = ' '.join(' '.join(p.extract_text() for p in PdfReader(path).pages).split())
    assert 'độ tọa độ' in content and 'Minh chứng cảnh báo theo ảnh' in content
    assert 'km/h' not in content and 'shared_clock' not in content
    with pytest.raises(ValueError):
        build_report(rows,rule_options={'distance_limit':500})
