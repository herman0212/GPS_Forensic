"""Kiểm tra nội dung bản đồ Folium mà không cần Internet."""
import csv
import folium
from core.map_view import create_map, export_map
from core.metadata import export_rows, load_dataset
from core.anomaly import analyze_rules
from tests.test_gps import record


def test_map_valid_markers_and_no_route(tmp_path):
    rows = [record('<script>bad</script>'), record('b', 1), record('invalid', 181)]
    result = create_map(rows)
    assert sum(isinstance(c, folium.Marker) for c in result._children.values()) == 2
    assert not any(isinstance(c, folium.PolyLine) for c in result._children.values())
    path = tmp_path / 'map.html'
    export_map(rows, path)
    html = path.read_text(encoding='utf-8')
    assert '<script>bad</script>' not in html
    assert '2025-01-01' in html
    assert 'GPS 0.0, 1.0' in html


def test_empty_map():
    assert not any(isinstance(c, folium.Marker) for c in create_map([])._children.values())


def test_export_optional_journey_annotation(tmp_path):
    rows = [record(), record('b')]
    rows[0].pop('journey_group')
    rows[1]['journey_group'] = 'confirmed'
    path = tmp_path / 'rows.csv'
    export_rows(rows, path)
    with path.open(encoding='utf-8-sig') as stream:
        assert list(csv.DictReader(stream))[1]['journey_group'] == 'confirmed'


def test_real_dataset_no_inferred_journey():
    rows = load_dataset('data/Image2GPS25/metadata.csv')
    alerts, pairs = analyze_rules(rows)
    assert not pairs
    assert not any(a['kind'] == 'speed_high' for a in alerts)
    assert sum(isinstance(c, folium.Marker) for c in create_map(rows)._children.values()) == 100
