"""Kiểm tra GPS và tính khoảng cách địa lý bằng Haversine."""
import math


def gps_decimal(dms, ref):
    """Đổi độ/phút/giây sang số thập phân, yêu cầu hướng GPS rõ ràng."""
    try:
        if ref not in ('N', 'S', 'E', 'W') or len(dms) != 3:
            return None
        degrees, minutes, seconds = [float(v) for v in dms]
        if degrees < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            return None
        result = degrees + minutes / 60 + seconds / 3600
        return -result if ref in ('S', 'W') else result
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def valid_gps(latitude, longitude):
    """Chỉ nhận hai số hữu hạn trong phạm vi địa lý."""
    try:
        lat, lon = float(latitude), float(longitude)
        return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180
    except (ValueError, TypeError):
        return False


def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách đường tròn lớn (km), bán kính Trái Đất 6371 km."""
    if not valid_gps(lat1, lon1) or not valid_gps(lat2, lon2):
        raise ValueError('Hai vị trí phải có GPS hợp lệ.')
    lat1, lon1, lat2, lon2 = map(math.radians, map(float, (lat1, lon1, lat2, lon2)))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    a = min(1.0, max(0.0, a))
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compare_positions(first, second, shared_clock=False):
    """Khoảng cách cho hai ảnh; vận tốc cần nhóm xác nhận và giờ so sánh được.

    shared_clock chỉ dùng khi người dùng xác nhận giờ không offset cùng cơ sở
    đồng hồ. Đây không phải phép tự gán múi giờ cho dữ liệu gốc.
    """
    from core.timeline import parse_time
    result = {'distance_km': None, 'delta_seconds': None, 'speed_kmh': None, 'reason': ''}
    if not valid_gps(first.get('latitude'), first.get('longitude')) or not valid_gps(second.get('latitude'), second.get('longitude')):
        result['reason'] = 'GPS thiếu hoặc không hợp lệ'
        return result
    result['distance_km'] = haversine(first['latitude'], first['longitude'], second['latitude'], second['longitude'])
    group = first.get('journey_group')
    if not group or group != second.get('journey_group'):
        result['reason'] = 'Chưa xác nhận cùng nhóm hành trình'
        return result
    start, end = parse_time(first.get('timestamp')), parse_time(second.get('timestamp'))
    if start is None or end is None:
        result['reason'] = 'Timestamp thiếu hoặc không hợp lệ'
        return result
    if (start.tzinfo is None) != (end.tzinfo is None):
        result['reason'] = 'Không so sánh giờ có offset với giờ chưa rõ múi giờ'
        return result
    if start.tzinfo is None and not shared_clock:
        result['reason'] = 'Chưa xác nhận cùng cơ sở đồng hồ cho giờ không offset'
        return result
    seconds = (end - start).total_seconds()
    result['delta_seconds'] = seconds
    if seconds <= 0:
        result['reason'] = 'Khoảng thời gian bằng 0' if seconds == 0 else 'Thứ tự thời gian đảo ngược'
        return result
    result['speed_kmh'] = result['distance_km'] / (seconds / 3600)
    return result
