"""Phân tích thời gian, giữ riêng giờ có và không có múi giờ."""
from collections import Counter
from datetime import datetime, timezone


def parse_time(value):
    """Đọc ISO 8601 hoặc EXIF; không cắt bỏ offset hay đoán múi giờ."""
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        try:
            return datetime.strptime(text, '%Y:%m:%d %H:%M:%S')
        except ValueError:
            return None


def time_key(stamp):
    """Chuẩn hóa giờ có offset về UTC để so sánh cùng một thời điểm."""
    if stamp.tzinfo is not None:
        return 'Có múi giờ', stamp.astimezone(timezone.utc)
    return 'Chưa rõ múi giờ', stamp


def build_timeline(records, start='', end=''):
    """Sắp xếp riêng hai nhóm; khoảng cách thời gian chỉ tính trong nhóm."""
    lower, upper = parse_time(start), parse_time(end)
    if (start and lower is None) or (end and upper is None):
        raise ValueError('Bộ lọc cần thời gian ISO 8601 hợp lệ.')
    if lower and upper:
        if time_key(lower)[0] != time_key(upper)[0] or lower > upper:
            raise ValueError('Hai mốc lọc phải cùng loại múi giờ và tăng dần.')
    counts = Counter(time_key(t) for r in records if (t := parse_time(r['timestamp'])))
    rows = []
    for record in records:
        raw = record['timestamp']
        stamp = parse_time(raw)
        row = dict(file=record['file'], timestamp=raw, source=record.get('timestamp_source', ''),
                   timezone='', delta_seconds='', status='', _stamp=stamp)
        if stamp is None:
            row['status'] = 'Thiếu timestamp' if not str(raw or '').strip() else 'Timestamp không hợp lệ'
        else:
            group, normalized = time_key(stamp)
            row['timezone'] = str(stamp.utcoffset()) if stamp.tzinfo else 'Chưa rõ múi giờ'
            if counts[(group, normalized)] > 1:
                row['status'] = 'Timestamp trùng'
            if lower and (group != time_key(lower)[0] or stamp < lower):
                continue
            if upper and (group != time_key(upper)[0] or stamp > upper):
                continue
        if stamp is None and (lower or upper):
            continue
        rows.append(row)
    rows.sort(key=lambda r: (time_key(r['_stamp']) if r['_stamp'] else ('~', datetime.max), r['file']))
    previous = {}
    for row in rows:
        stamp = row.pop('_stamp')
        if stamp:
            group, normalized = time_key(stamp)
            if group in previous:
                row['delta_seconds'] = (normalized - previous[group]).total_seconds()
            previous[group] = normalized
    return rows
