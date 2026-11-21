"""Kiểm tra và đối chiếu metadata GPS, không sửa dữ liệu nguồn."""
import math


def gps_decimal(dms, ref):
    """Đổi DMS sang độ thập phân; thiếu/sai dữ liệu trả về None."""
    try:
        if isinstance(ref, bytes):
            ref = ref.decode('ascii')
        if not isinstance(ref, str) or not isinstance(dms, (list, tuple)) or len(dms) != 3:
            return None
        ref = ref.strip().upper()
        if ref not in ('N', 'S', 'E', 'W') or any(isinstance(v, bool) for v in dms):
            return None
        degrees, minutes, seconds = [float(v) for v in dms]
        if not all(math.isfinite(v) for v in (degrees, minutes, seconds)):
            return None
        if degrees < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
            return None
        result = degrees + minutes / 60 + seconds / 3600
        if result > (90 if ref in ('N', 'S') else 180):
            return None
        return -result if ref in ('S', 'W') else result
    except (ValueError, TypeError, ZeroDivisionError, OverflowError, UnicodeError):
        return None


def normalize_gps(latitude, longitude):
    """Trả bản chuẩn hóa riêng và trạng thái valid/missing/invalid.

    raw_* giữ bằng chứng đầu vào; không làm tròn, kẹp phạm vi hoặc ghi EXIF.
    """
    raw = (latitude, longitude)
    missing = [v is None or (isinstance(v, str) and not v.strip()) for v in raw]
    values, invalid = [], False
    for value, absent, limit in zip(raw, missing, (90, 180)):
        if absent:
            values.append(None)
            continue
        try:
            if isinstance(value, bool):
                raise ValueError('Không nhận bool')
            number = float(value)
            if not math.isfinite(number) or not -limit <= number <= limit:
                raise ValueError('Ngoài phạm vi')
            values.append(number)
        except (ValueError, TypeError, OverflowError):
            invalid = True
            values.append(None)
    status = 'invalid' if invalid else ('missing' if any(missing) else 'valid')
    return dict(status=status, latitude=values[0] if status == 'valid' else None,
                longitude=values[1] if status == 'valid' else None,
                raw_latitude=latitude, raw_longitude=longitude, provided=not all(missing))


def valid_gps(latitude, longitude):
    """Chỉ nhận cặp tọa độ hữu hạn trong phạm vi địa lý."""
    return normalize_gps(latitude, longitude)['status'] == 'valid'


def validate_tolerance(tolerance):
    """Ngưỡng kỹ thuật tính bằng độ tọa độ, cho phép 0 để so khớp chính xác."""
    try:
        value = float(tolerance)
        if isinstance(tolerance, bool) or not math.isfinite(value) or value < 0:
            raise ValueError()
        return value
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Ngưỡng sai lệch phải là số hữu hạn không âm, đơn vị độ tọa độ.') from None


def gps_pair(source):
    """Đọc dict latitude/longitude hoặc lat/lon, hay cặp hai giá trị."""
    if isinstance(source, dict):
        if 'raw_latitude' in source and 'raw_longitude' in source:
            return source['raw_latitude'], source['raw_longitude']
        return source.get('latitude', source.get('lat')), source.get('longitude', source.get('lon'))
    if isinstance(source, (list, tuple)) and len(source) == 2:
        return source[0], source[1]
    return None, None


def compare_gps_sources(csv_gps, exif_gps, tolerance=0.0001):
    """So |lat_csv-lat_exif| và |lon_csv-lon_exif|, không tính cự ly.

    Thiếu hoặc sai bất kỳ nguồn nào => insufficient; không kết luận giống/khác.
    """
    tolerance = validate_tolerance(tolerance)
    csv = normalize_gps(*gps_pair(csv_gps))
    exif = normalize_gps(*gps_pair(exif_gps))
    result = dict(csv=csv, exif=exif, gps_tolerance_deg=tolerance,
                  status='insufficient', latitude_delta_deg=None, longitude_delta_deg=None,
                  reason='Không đủ dữ liệu GPS hợp lệ từ cả CSV và EXIF để đối chiếu.')
    if csv['status'] == exif['status'] == 'valid':
        lat_delta = abs(csv['latitude'] - exif['latitude'])
        lon_delta = abs(csv['longitude'] - exif['longitude'])
        # isclose chỉ tránh sai số float tại đúng biên ngưỡng, không đổi đơn vị.
        exceeded = any(d > tolerance and not (tolerance > 0 and math.isclose(d, tolerance, rel_tol=1e-12, abs_tol=1e-15))
                       for d in (lat_delta, lon_delta))
        result.update(status='difference' if exceeded else 'match', latitude_delta_deg=lat_delta,
                      longitude_delta_deg=lon_delta,
                      reason='Hai nguồn khác nhau vượt ngưỡng kỹ thuật.' if exceeded else 'Hai nguồn khớp trong ngưỡng kỹ thuật.')
    return result


def gps_sources(record):
    """Giữ tách nguồn; tọa độ chưa rõ nguồn không được đổi nhãn thành EXIF."""
    csv = record.get('csv_original', record.get('csv_gps'))
    exif = record.get('exif', record.get('exif_gps'))
    reference = record.get('reference_gps')
    if csv is None and exif is None and reference is None:
        reference = dict(latitude=record.get('latitude'), longitude=record.get('longitude'))
    sources = dict(CSV=normalize_gps(*gps_pair(csv)), EXIF=normalize_gps(*gps_pair(exif)),
                   reference=normalize_gps(*gps_pair(reference)))
    if isinstance(exif, dict) and exif.get('gps_parse_invalid'):
        sources['EXIF'].update(status='invalid', provided=True, raw_dms=exif.get('gps_raw', {}))
    return sources
