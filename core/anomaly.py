"""GPS Forensics: dữ liệu thiếu, sai và bất nhất được báo riêng theo nguồn."""
from collections import Counter
from core.gps import gps_sources, compare_gps_sources, validate_tolerance
from core.timeline import parse_time, time_key, missing_time


def analyze_rules(records, gps_tolerance_deg=0.0001):
    """Trả dict alerts, comparisons, gps_summary. Không thay đổi bản ghi gốc."""
    tolerance = validate_tolerance(gps_tolerance_deg)
    alerts, comparisons = [], []
    summary = dict(valid=0, missing=0, invalid=0, csv_present=0, csv_valid=0,
                   exif_present=0, exif_valid=0, comparable=0, different=0, insufficient=0)
    times = [parse_time(r.get('timestamp')) for r in records]
    counts = Counter(time_key(t) for t in times if t is not None)
    offsets = {t.utcoffset() for t in times if t is not None and t.tzinfo is not None}
    mixed = bool(offsets) and any(t is not None and t.tzinfo is None for t in times)

    def add(record, kind, description, value, level='Cảnh báo', source=''):
        alerts.append(dict(file=record.get('file', ''), kind=kind, description=description,
                           value=value, level=level, source=source))

    for record, stamp in zip(records, times):
        sources = gps_sources(record)
        statuses = [s['status'] for s in sources.values()]
        summary['valid'] += 'valid' in statuses
        summary['missing'] += all(s == 'missing' for s in statuses)
        summary['invalid'] += 'invalid' in statuses
        for name in ('CSV', 'EXIF'):
            summary[name.lower() + '_present'] += sources[name]['provided']
            summary[name.lower() + '_valid'] += sources[name]['status'] == 'valid'
        for name, gps in sources.items():
            if name == 'reference' and not gps['provided']:
                continue
            evidence = dict(source=name, latitude=gps['raw_latitude'], longitude=gps['raw_longitude'])
            if gps.get('raw_dms'):
                evidence['raw_dms'] = gps['raw_dms']
            if gps['status'] == 'missing':
                add(record, 'gps_missing', f'GPS {name} thiếu hoặc chưa đủ hai thành phần; không suy đoán từ nguồn khác.',
                    evidence, 'Thông tin' if 'valid' in statuses else 'Cảnh báo', name)
            elif gps['status'] == 'invalid':
                add(record, 'gps_invalid', f'GPS {name} không hợp lệ (phạm vi, kiểu dữ liệu hoặc số không hữu hạn).', evidence, source=name)
        # Dùng raw_* để không làm mất trạng thái invalid đã phát hiện.
        comparison = compare_gps_sources((sources['CSV']['raw_latitude'], sources['CSV']['raw_longitude']),
                                         (sources['EXIF']['raw_latitude'], sources['EXIF']['raw_longitude']), tolerance)
        row = dict(file=record.get('file', ''), timestamp=record.get('timestamp', ''),
                   csv_latitude=sources['CSV']['raw_latitude'], csv_longitude=sources['CSV']['raw_longitude'],
                   csv_status=sources['CSV']['status'], exif_latitude=sources['EXIF']['raw_latitude'],
                   exif_longitude=sources['EXIF']['raw_longitude'], exif_status=sources['EXIF']['status'],
                   reference_latitude=sources['reference']['raw_latitude'], reference_longitude=sources['reference']['raw_longitude'],
                   reference_status=sources['reference']['status'], status=comparison['status'],
                   latitude_delta_deg=comparison['latitude_delta_deg'], longitude_delta_deg=comparison['longitude_delta_deg'],
                   gps_tolerance_deg=tolerance, reason=comparison['reason'])
        comparisons.append(row)
        summary['comparable'] += row['status'] != 'insufficient'
        summary['different'] += row['status'] == 'difference'
        summary['insufficient'] += row['status'] == 'insufficient'
        if row['status'] == 'difference':
            add(record, 'gps_source_difference', 'GPS EXIF và CSV lệch vượt ngưỡng độ tọa độ; không đủ để kết luận giả mạo.',
                dict(latitude_delta_deg=row['latitude_delta_deg'], longitude_delta_deg=row['longitude_delta_deg'],
                     gps_tolerance_deg=tolerance), source='CSV / EXIF')
        if stamp is None:
            missing = missing_time(record.get('timestamp'))
            add(record, 'time_missing' if missing else 'time_invalid', 'Thiếu timestamp' if missing else 'Timestamp không hợp lệ',
                record.get('timestamp', ''), source=record.get('timestamp_source', ''))
        else:
            if counts[time_key(stamp)] > 1:
                add(record, 'time_duplicate', 'Timestamp trùng; không suy luận quan hệ giữa các ảnh.', record['timestamp'])
            if stamp.tzinfo is None:
                add(record, 'timezone_unknown', 'Timestamp chưa rõ múi giờ; không tự gán UTC hoặc GMT+7.', record['timestamp'], 'Thông tin')
            csv_metadata = record.get('csv_original') or {}
            exif_metadata = record.get('exif') or {}
            csv_stamp = parse_time(csv_metadata.get('timestamp') or csv_metadata.get('timestamp_raw'))
            exif_stamp = parse_time(exif_metadata.get('timestamp'))
            source_difference = (csv_stamp is not None and exif_stamp is not None
                                 and csv_stamp.utcoffset() != exif_stamp.utcoffset())
            if mixed or len(offsets) > 1 or source_difference:
                add(record, 'timezone_difference', 'Có khác biệt thông tin múi giờ trong tập hoặc giữa CSV và EXIF.',
                    dict(timestamp=record['timestamp'], offset=str(stamp.utcoffset()) if stamp.tzinfo else None,
                         csv_timestamp=csv_metadata.get('timestamp') or csv_metadata.get('timestamp_raw'),
                         exif_timestamp=exif_metadata.get('timestamp')), 'Thông tin')
    return dict(alerts=alerts, comparisons=comparisons, gps_summary=summary)
