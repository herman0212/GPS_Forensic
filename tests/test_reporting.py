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
