"""Luật cảnh báo GPS/thời gian; cảnh báo không phải bằng chứng giả mạo."""
import math
from collections import Counter
from core.gps import valid_gps, haversine, compare_positions
from core.timeline import parse_time, time_key


def analyze_rules(records, distance_limit=500, speed_limit=900, gps_difference=0.1, shared_clock=False):
    """Trả về cảnh báo và các cặp liên tiếp trong nhóm do người dùng xác nhận.

    Không ghép các ảnh độc lập thành hành trình. Giờ aware và naive được giữ
    riêng; GPS không hợp lệ không bị bỏ qua để nối hai đầu khoảng trống.
    """
    for value in (distance_limit, speed_limit, gps_difference):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Ngưỡng cảnh báo phải là số hữu hạn lớn hơn 0.')
    alerts, pairs = [], []

    def add(record, kind, description, value='', level='Cảnh báo'):
        alerts.append(dict(file=record['file'], kind=kind, description=description, value=value, level=level))

    times = [parse_time(r.get('timestamp')) for r in records]
    counts = Counter(time_key(t) for t in times if t)
    offsets = {t.utcoffset() for t in times if t and t.tzinfo is not None}
    mixed = any(t and t.tzinfo is None for t in times) and bool(offsets)
    groups = {}
    for record, stamp in zip(records, times):
        raw = record.get('csv_original')
        lat, lon = (raw.get('lat'), raw.get('lon')) if raw is not None else (record.get('latitude'), record.get('longitude'))
        if lat is None or lon is None or str(lat).strip() == '' or str(lon).strip() == '':
            add(record, 'gps_missing', 'Thiếu GPS')
        elif not valid_gps(lat, lon):
            add(record, 'gps_invalid', 'GPS không hợp lệ', f'{lat}, {lon}')
        if stamp is None:
            missing = not str(record.get('timestamp') or '').strip()
            add(record, 'time_missing' if missing else 'time_invalid', 'Thiếu timestamp' if missing else 'Timestamp không hợp lệ', record.get('timestamp', ''))
        else:
            if counts[time_key(stamp)] > 1:
                add(record, 'time_duplicate', 'Timestamp trùng (không chứng minh cùng hành trình)', record['timestamp'])
            if stamp.tzinfo is None:
                add(record, 'timezone_unknown', 'Không biết múi giờ; không tự gán UTC', level='Thông tin')
            if mixed or len(offsets) > 1:
                add(record, 'timezone_difference', 'Tập dữ liệu có khác biệt thông tin múi giờ', level='Thông tin')
            if record.get('journey_group'):
                key = (record['journey_group'], time_key(stamp)[0])
                groups.setdefault(key, []).append(record)
        exif = record.get('exif', {})
        if raw is not None and valid_gps(lat, lon) and valid_gps(exif.get('latitude'), exif.get('longitude')):
            distance = haversine(lat, lon, exif['latitude'], exif['longitude'])
            if distance > gps_difference:
                add(record, 'gps_source_difference', 'GPS EXIF khác GPS CSV (km)', distance)
    for (group, _), items in groups.items():
        items = sorted(items, key=lambda r: time_key(parse_time(r['timestamp']))[1])
        for first, second in zip(items, items[1:]):
            result = compare_positions(first, second, shared_clock)
            pairs.append(dict(first=first['file'], second=second['file'], group=group, **result))
            if result['distance_km'] is not None and result['distance_km'] > distance_limit:
                add(second, 'distance_large', f'Khoảng cách lớn từ {first["file"]} (km)', result['distance_km'])
            if result['delta_seconds'] == 0:
                add(second, 'time_zero', f'Khoảng thời gian bằng 0 với {first["file"]}', 0)
            if result['speed_kmh'] is not None and result['speed_kmh'] > speed_limit:
                add(second, 'speed_high', f'Vận tốc đường chim bay lớn từ {first["file"]} (km/h)', result['speed_kmh'], 'Cao')
    return alerts, pairs
