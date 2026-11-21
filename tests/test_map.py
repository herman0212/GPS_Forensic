"""Marker phân biệt nguồn, không vẽ tuyến, nội dung popup an toàn."""
import csv
import folium
from core.map_view import create_map, export_map
from core.metadata import export_rows, load_dataset
from core.anomaly import analyze_rules
from tests.test_gps import record


def markers(result):
    found = []
    for child in result._children.values():
        if isinstance(child,folium.Marker):
            found.append(child)
        elif hasattr(child,'_children'):
            found.extend(markers(child))
    return found


def test_map_valid_markers_and_no_route(tmp_path):
    rows = [record('<script>bad</script>'),record('b',1),record('invalid',181)]
    result = create_map(rows)
    assert len(markers(result)) == 2
    assert not any(isinstance(c,folium.PolyLine) for c in result._children.values())
    path = tmp_path/'map.html'
    export_map(rows,path)
    html = path.read_text(encoding='utf-8')
    assert '<script>bad</script>' not in html
    assert '2025-01-01' in html and 'GPS 0.0, 1.0' in html


def test_both_sources_have_distinct_markers_and_colors():
    row = record()
    row['csv_original'] = {'lat':1,'lon':2}
    result = create_map([row])
    assert len(markers(result)) == 2
    html = result.get_root().render()
    assert 'CSV' in html and 'EXIF' in html and 'blue' in html and 'green' in html


def test_invalid_csv_does_not_hide_valid_exif():
    row = record()
    row['csv_original'] = {'lat':91,'lon':0}
    assert len(markers(create_map([row]))) == 1


def test_empty_map():
    assert not markers(create_map([]))


def test_export_optional_reference_annotation(tmp_path):
    rows = [record(),record('b')]
    rows[1]['reference_note'] = 'Tham chiếu chưa xác minh'
    path = tmp_path/'rows.csv'
    export_rows(rows,path)
    with path.open(encoding='utf-8-sig') as stream:
        assert list(csv.DictReader(stream))[1]['reference_note'] == 'Tham chiếu chưa xác minh'


def test_real_dataset_separates_sources():
    rows = load_dataset('data/Image2GPS25/metadata.csv')
    result = analyze_rules(rows)
    assert result['gps_summary']['csv_valid'] == 100
    assert result['gps_summary']['exif_valid'] == result['gps_summary']['comparable'] == 0
    assert result['gps_summary']['insufficient'] == 100
    assert len(markers(create_map(rows))) == 100
