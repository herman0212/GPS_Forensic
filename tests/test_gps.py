"""Các giá trị Haversine có thể kiểm tra độc lập bằng kiến thức địa lý."""
import pytest
from core.gps import haversine, compare_positions


def record(name='a', lon=0, stamp='2025-01-01T00:00:00Z', group=''):
    return dict(file=name, latitude=0, longitude=lon, timestamp=stamp, journey_group=group)


def test_same_position():
    assert haversine(10, 20, 10, 20) == 0


def test_known_distance():
    # Một độ kinh tuyến tại xích đạo xấp xỉ 111,195 km.
    assert haversine(0, 0, 0, 1) == pytest.approx(111.1949, abs=0.001)
    # London đến New York khoảng 5570 km theo đường tròn lớn.
    assert haversine(51.5074, -0.1278, 40.7128, -74.0060) == pytest.approx(5570.22, abs=1)


def test_antipodal_and_date_line():
    assert haversine(0, 0, 0, 180) == pytest.approx(20015.087, abs=0.01)
    assert haversine(0, 179, 0, -179) == pytest.approx(222.39, abs=0.01)


@pytest.mark.parametrize('coords', [(91, 0, 0, 0), (0, 181, 0, 0), (None, 0, 0, 0), (float('nan'), 0, 0, 0), (0, 0, float('inf'), 0)])
def test_invalid_coordinates(coords):
    with pytest.raises(ValueError):
        haversine(*coords)


def test_distance_does_not_imply_journey():
    result = compare_positions(record(), record('b', 1, '2025-01-01T01:00:00Z'))
    assert result['distance_km'] > 100
    assert result['speed_kmh'] is None
    assert result['delta_seconds'] is None


def test_speed_confirmed_group():
    result = compare_positions(record(group='trip'), record('b', 1, '2025-01-01T08:00:00+07:00', 'trip'))
    assert result['delta_seconds'] == 3600
    assert result['speed_kmh'] == pytest.approx(111.1949, abs=0.001)


def test_naive_clock_requires_confirmation():
    a = record(stamp='2025-01-01T00:00:00', group='trip')
    b = record('b', 1, '2025-01-01T01:00:00', 'trip')
    assert compare_positions(a, b)['speed_kmh'] is None
    assert compare_positions(a, b, True)['speed_kmh'] > 100


@pytest.mark.parametrize('stamp', ['', 'bad', '2025-01-01T01:00:00', '2025-01-01T00:00:00Z', '2024-12-31T23:00:00Z'])
def test_unusable_time_never_produces_speed(stamp):
    assert compare_positions(record(group='trip'), record('b', 1, stamp, 'trip'), True)['speed_kmh'] is None


def test_different_groups():
    assert compare_positions(record(group='one'), record('b', 1, '2025-01-01T01:00:00Z', 'two'))['speed_kmh'] is None
