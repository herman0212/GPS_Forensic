"""Kiểm tra các luật với dữ liệu nhỏ, không sửa dữ liệu nguồn."""
from copy import deepcopy
import pytest
from core.anomaly import analyze_rules
from tests.test_gps import record


def kinds(alerts):
    return {row['kind'] for row in alerts}


def test_missing_invalid_and_duplicates():
    rows = [record('a', stamp=''), record('b', stamp='bad'), record('c'), record('d')]
    rows[0]['latitude'] = None
    rows[1]['longitude'] = 181
    alerts, pairs = analyze_rules(rows)
    assert {'gps_missing', 'gps_invalid', 'time_missing', 'time_invalid', 'time_duplicate'} <= kinds(alerts)
    assert not pairs
    assert all({'file', 'kind', 'description', 'value', 'level'} <= set(a) for a in alerts)


def test_csv_invalid_gps_is_not_mislabeled_missing():
    row = record()
    row.update(latitude=None, longitude=None, csv_original={'lat': 'NaN', 'lon': '0'})
    assert 'gps_invalid' in kinds(analyze_rules([row])[0])


def test_thresholds_and_no_mutation():
    rows = [record(group='trip'), record('b', 10, '2025-01-01T01:00:00Z', 'trip')]
    original = deepcopy(rows)
    alerts, pairs = analyze_rules(rows, distance_limit=100, speed_limit=500)
    assert {'distance_large', 'speed_high'} <= kinds(alerts)
    assert pairs[0]['speed_kmh'] > 1000
    assert rows == original
    assert not kinds(analyze_rules(rows, distance_limit=2000, speed_limit=2000)[0])


def test_zero_and_offsets():
    rows = [record(group='trip'), record('b', 1, '2025-01-01T07:00:00+07:00', 'trip')]
    alerts, pairs = analyze_rules(rows)
    assert {'time_zero', 'time_duplicate', 'timezone_difference'} <= kinds(alerts)
    assert pairs[0]['speed_kmh'] is None


def test_never_group_by_timezone_alone():
    rows = [record(), record('b', 100, '2025-01-01T00:00:01Z')]
    alerts, pairs = analyze_rules(rows)
    assert not pairs
    assert 'speed_high' not in kinds(alerts)


def test_mixed_clocks_are_not_compared():
    rows = [record(group='trip'), record('b', 1, '2025-01-01T01:00:00', 'trip')]
    alerts, pairs = analyze_rules(rows, shared_clock=True)
    assert not pairs
    assert 'timezone_difference' in kinds(alerts)


def test_gps_source_difference():
    row = record()
    row['csv_original'] = {'lat': '0', 'lon': '0'}
    row['exif'] = {'latitude': 0, 'longitude': 1}
    assert 'gps_source_difference' in kinds(analyze_rules([row])[0])
    assert 'gps_source_difference' not in kinds(analyze_rules([row], gps_difference=200)[0])


def test_invalid_middle_gps_does_not_bridge():
    rows = [record(group='trip'), record('b', 181, '2025-01-01T01:00:00Z', 'trip'),
            record('c', 10, '2025-01-01T02:00:00Z', 'trip')]
    assert all(p['speed_kmh'] is None for p in analyze_rules(rows)[1])


@pytest.mark.parametrize('options', [{'distance_limit': 0}, {'speed_limit': -1}, {'gps_difference': float('nan')}])
def test_invalid_thresholds(options):
    with pytest.raises(ValueError):
        analyze_rules([], **options)
