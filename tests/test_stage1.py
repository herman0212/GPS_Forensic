"""Các ca kiểm thử nhỏ chạy bằng pytest."""
import csv
import hashlib
import pytest
from PIL import Image
from core.gps import valid_gps
from core.metadata import load_dataset, export_rows
from core.timeline import parse_time, build_timeline


def test_gps():
    assert valid_gps(0, 0)
    assert not valid_gps(91, 0)
    assert not valid_gps(float('nan'), 0)


def test_time():
    assert parse_time('') is None
    assert parse_time('2025-11-22T14:43:19').tzinfo is None
    assert parse_time('2025-11-22T14:43:19+07:00').utcoffset().total_seconds() == 25200
    assert parse_time('2025-11-22T14:43:19garbage') is None


def test_timeline():
    records = [{'file': str(i), 'timestamp': t} for i, t in enumerate([
        '', 'bad', '2025-01-01T00:00:00', '2025-01-01T00:00:00',
        '2025-01-01T00:00:00Z', '2025-01-01T07:00:00+07:00'])]
    rows = build_timeline(records)
    assert sum(r['status'] == 'Timestamp trùng' for r in rows) == 4
    assert any(r['status'] == 'Thiếu timestamp' for r in rows)
    assert any(r['status'] == 'Timestamp không hợp lệ' for r in rows)
    assert len(build_timeline(records, '2025-01-01T00:00:00Z')) == 2
    with pytest.raises(ValueError):
        build_timeline(records, 'bad')


def test_csv_and_preservation(tmp_path):
    folder = tmp_path / 'images'
    folder.mkdir()
    image = folder / 'a.jpg'
    Image.new('RGB', (10, 10)).save(image)
    before = hashlib.sha256(image.read_bytes()).hexdigest()
    path = tmp_path / 'metadata.csv'
    fields = ['filename', 'lat', 'lon', 'gps_altitude', 'timestamp', 'timestamp_raw', 'camera_make', 'camera_model']
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name in ['a.jpg', 'missing.jpg', '../escape.jpg']:
            writer.writerow(dict(filename=name, lat='0', lon='0', timestamp='2025-01-01T00:00:00'))
    records = load_dataset(path)
    assert records[0]['timestamp_source'] == 'CSV'
    assert records[0]['exif']['timestamp'] == ''
    assert records[1]['warnings']
    assert records[2]['path'] == ''
    assert hashlib.sha256(image.read_bytes()).hexdigest() == before
    export_rows(records, tmp_path / 'report.csv')
    assert len(list(csv.DictReader((tmp_path / 'report.csv').open(encoding='utf-8-sig')))) == 3


def test_real_dataset():
    records = load_dataset('data/Image2GPS25/metadata.csv')
    assert len(records) == 100
    assert all(r['format'] == 'JPEG' for r in records)
    assert len(build_timeline(records)) == 100
