"""Nhập CSV với nguồn gốc rõ ràng, chỉ đọc ảnh gốc."""
import csv
import json
import math
from pathlib import Path
from PIL import Image, ExifTags
from core.gps import valid_gps
from core.timeline import parse_time


def number(value):
    """Giá trị rỗng, NaN và vô cực không phải số đo hợp lệ."""
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def read_exif(path):
    """Đọc IFD EXIF lồng nhau mà Pillow không đưa vào IFD gốc."""
    with Image.open(path) as image:
        image.load()
        exif = image.getexif()
        tags = dict(exif)
        tags.update(exif.get_ifd(0x8769))
        gps = exif.get_ifd(0x8825)
        from core.gps import gps_decimal
        lat = gps_decimal(gps.get(2), gps.get(1)) if gps else None
        lon = gps_decimal(gps.get(4), gps.get(3)) if gps else None
        if gps.get(1) not in ('N', 'S', b'N', b'S'):
            lat = None
        if gps.get(3) not in ('E', 'W', b'E', b'W'):
            lon = None
        gps_parse_invalid = (2 in gps and lat is None) or (4 in gps and lon is None)
        stamp = tags.get(36867) or tags.get(36868) or tags.get(306) or ''
        offset = tags.get(36881) or tags.get(36880) or ''
        if stamp and offset:
            try:
                stamp = str(stamp)
                stamp = stamp[:10].replace(':', '-') + stamp[10:] + str(offset)
            except ValueError:
                pass
        altitude = number(gps.get(6))
        if altitude is not None and gps.get(5) in (1, b'\x01'):
            altitude = -altitude
        return {'timestamp': str(stamp), 'offset': str(offset), 'latitude': lat,
                'longitude': lon, 'camera': str(tags.get(272, '')),
                'altitude': altitude, 'format': image.format,
                'size': f'{image.width}x{image.height}',
                'tags': {str(ExifTags.TAGS.get(k, k)): str(v) for k, v in tags.items()},
                'gps_raw': {str(ExifTags.GPSTAGS.get(k, k)): str(v) for k, v in gps.items()},
                'gps_parse_invalid': gps_parse_invalid}


def load_dataset(csv_path):
    """Ghép filename trong images/; giữ nguyên toàn bộ dòng CSV và EXIF riêng."""
    csv_path = Path(csv_path).resolve()
    image_dir = (csv_path.parent / 'images').resolve()
    records = []
    with csv_path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'filename', 'lat', 'lon', 'gps_altitude', 'timestamp',
                    'timestamp_raw', 'camera_make', 'camera_model'}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError('CSV thiếu cột: ' + ', '.join(sorted(missing)))
        seen = set()
        for line, raw in enumerate(reader, 2):
            warnings = []
            filename = (raw.get('filename') or '').strip()
            path = (image_dir / filename).resolve()
            safe = bool(filename) and path.parent == image_dir and '\\' not in filename and '/' not in filename
            if filename in seen:
                warnings.append('Filename trùng trong CSV')
            seen.add(filename)
            exif = {}
            if not safe:
                warnings.append('Filename không hợp lệ')
            else:
                try:
                    exif = read_exif(path)
                except (OSError, ValueError, TypeError, SyntaxError) as error:
                    warnings.append(f'Không đọc được ảnh: {error}')
            lat, lon = number(raw.get('lat')), number(raw.get('lon'))
            if not valid_gps(lat, lon):
                warnings.append('GPS CSV thiếu hoặc không hợp lệ')
                lat = lon = None
            stamp = raw.get('timestamp') or raw.get('timestamp_raw') or ''
            if not parse_time(stamp):
                warnings.append('Timestamp CSV thiếu hoặc không hợp lệ')
            elif parse_time(stamp).tzinfo is None:
                warnings.append('Timestamp CSV chưa rõ múi giờ')
            altitude = number(raw.get('gps_altitude'))
            if altitude is None:
                warnings.append('Altitude CSV thiếu hoặc không hợp lệ')
            camera = ' '.join(filter(None, [raw.get('camera_make'), raw.get('camera_model')]))
            if not camera:
                warnings.append('Thiếu camera CSV')
            if not exif.get('tags'):
                warnings.append('Ảnh không có EXIF; CSV không phải EXIF')
            records.append(dict(file=filename, path=str(path) if safe else '', csv_source=str(csv_path),
                                csv_line=line, csv_original=raw, exif=exif, timestamp=stamp,
                                timestamp_source='CSV', latitude=lat, longitude=lon, altitude=altitude,
                                camera=camera, offset='', format=exif.get('format', ''), size=exif.get('size', ''),
                                jpeg_recompress_mae=None, warnings=warnings))
    return records


def export_rows(rows, path):
    """Xuất CSV, giữ cấu trúc nguồn lồng nhau dưới dạng chuỗi JSON."""
    if not rows:
        raise ValueError('Không có dữ liệu để xuất.')
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                             for k, v in row.items()})
