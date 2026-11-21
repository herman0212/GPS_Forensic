"""Luật GPS/timestamp, nguồn dữ liệu và bảo toàn đầu vào."""
from copy import deepcopy
import pytest
from core.anomaly import analyze_rules
from tests.test_gps import record


def kinds(result):
    return {row['kind'] for row in result['alerts']}


def test_missing_invalid_and_duplicates():
    rows = [record('a',stamp=''),record('b',stamp='bad'),record('c'),record('d')]
    rows[0]['exif']['latitude'] = None
    rows[1]['exif']['longitude'] = 181
    result = analyze_rules(rows)
    assert {'gps_missing','gps_invalid','time_missing','time_invalid','time_duplicate'} <= kinds(result)
    assert len(result['comparisons']) == 4
    assert all({'file','kind','description','value','level','source'} <= set(a) for a in result['alerts'])


def test_csv_invalid_not_missing():
    row = record()
    row.update(csv_original={'lat':'NaN','lon':'0'})
    result = analyze_rules([row])
    assert any(a['kind']=='gps_invalid' and a['source']=='CSV' for a in result['alerts'])
    assert result['comparisons'][0]['status'] == 'insufficient'


def test_thresholds_and_no_mutation():
    row = record(lon=106)
    row['csv_original'] = {'lat':0.001,'lon':106}
    before = deepcopy(row)
    assert 'gps_source_difference' in kinds(analyze_rules([row]))
    assert 'gps_source_difference' not in kinds(analyze_rules([row],gps_tolerance_deg=0.01))
    assert row == before


def test_equivalent_times_with_different_offsets():
    result = analyze_rules([record('a'),record('b',stamp='2025-01-01T07:00:00+07:00')])
    assert {'time_duplicate','timezone_difference'} <= kinds(result)


def test_naive_and_aware_time_are_not_assumed_equivalent():
    result = analyze_rules([record('a'),record('b',stamp='2025-01-01T00:00:00')])
    assert {'timezone_difference','timezone_unknown'} <= kinds(result)
    assert 'time_duplicate' not in kinds(result)


def test_csv_gps_does_not_become_exif():
    row = dict(file='csv.jpg',timestamp='',latitude=10,longitude=106,
               csv_original={'lat':'10','lon':'106'},exif={})
    result = analyze_rules([row])
    assert result['gps_summary']['valid'] == result['gps_summary']['csv_valid'] == 1
    assert result['gps_summary']['exif_present'] == 0
    assert result['gps_summary']['insufficient'] == 1
    missing = [a for a in result['alerts'] if a['kind']=='gps_missing']
    assert len(missing) == 1 and missing[0]['source']=='EXIF'
    assert 'gps_source_difference' not in kinds(result)


def test_source_differences_with_full_evidence():
    row = record()
    row['csv_original'] = {'lat':0,'lon':1}
    result = analyze_rules([row])
    alert = next(a for a in result['alerts'] if a['kind']=='gps_source_difference')
    assert alert['value']['longitude_delta_deg'] == 1
    assert result['gps_summary']['comparable'] == result['gps_summary']['different'] == 1


def test_source_less_reference_is_not_relabeled_exif():
    result = analyze_rules([dict(file='unknown',timestamp='',latitude=10,longitude=106)])
    assert result['gps_summary']['valid'] == 1
    assert result['gps_summary']['csv_present'] == result['gps_summary']['exif_present'] == 0
    assert result['comparisons'][0]['reference_status'] == 'valid'


def test_numeric_zero_timestamp_is_invalid_not_missing():
    result = analyze_rules([record(stamp=0)])
    assert 'time_invalid' in kinds(result)
    assert 'time_missing' not in kinds(result)


@pytest.mark.parametrize('value',[-1,float('nan'),float('inf'),None,True])
def test_invalid_threshold(value):
    with pytest.raises(ValueError):
        analyze_rules([],gps_tolerance_deg=value)


@pytest.mark.parametrize('csv_time', ['2025-01-01T00:00:00Z', '2025-01-01T00:00:00'])
def test_timezone_difference_between_sources_in_one_record(csv_time):
    row = record(stamp=csv_time)
    row['csv_original'] = {'lat':0,'lon':0,'timestamp':csv_time}
    row['exif']['timestamp'] = '2025-01-01T07:00:00+07:00'
    result = analyze_rules([row])
    alert = next(a for a in result['alerts'] if a['kind']=='timezone_difference')
    assert alert['value']['csv_timestamp'] == csv_time
    assert alert['value']['exif_timestamp'] == row['exif']['timestamp']
