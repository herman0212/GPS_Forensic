"""Hàm batch độc lập Qt; lỗi từng ảnh không dừng toàn bộ tác vụ."""
from pathlib import Path
from time import perf_counter
from core.integrity import sha256_file, annotate_duplicates
from core.jpeg_analysis import image_information, inspect_jpeg_structure, recompress_jpeg
from core.metadata import read_exif

EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp'}


def list_images(folder, recursive=False):
    """Quét tùy chọn thư mục con; giữ WebP đã được hỗ trợ từ bản cũ."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError('Thư mục ảnh không tồn tại.')
    paths = folder.rglob('*') if recursive else folder.glob('*')
    return sorted(p for p in paths if p.is_file() and p.suffix.lower() in EXTENSIONS)


def analyze_file(path, quality=90):
    """Hash trước/sau kể cả khi giải mã lỗi; tất cả thao tác ảnh chỉ đọc."""
    path = Path(path)
    row = dict(file=path.name, path=str(path.resolve()), success=False, error='',
               sha256_before='', sha256_after='', hash_unchanged=None,
               timestamp='', timestamp_source='EXIF', offset='', latitude=None,
               longitude=None, camera='', format='', size='', mode='', file_bytes=None,
               jpeg_recompress_mae=None, warnings=[])
    try:
        row['sha256_before'] = sha256_file(path)
        # JPEG nhận diện theo chữ ký, vẫn kiểm tra cấu trúc khi Pillow không mở được.
        with path.open('rb') as stream:
            is_jpeg = stream.read(2) == b'\xff\xd8'
        if is_jpeg:
            row['jpeg_structure'] = inspect_jpeg_structure(path)
        info = image_information(path)
        row.update(info)
        row['size'] = f'{info["width"]}x{info["height"]}'
        exif = read_exif(path)
        row['exif'] = exif
        for key in ('timestamp', 'offset', 'latitude', 'longitude', 'camera', 'altitude'):
            row[key] = exif.get(key)
        from core.gps import valid_gps
        from core.timeline import parse_time
        if not valid_gps(row['latitude'], row['longitude']):
            row['warnings'].append('GPS EXIF thiếu hoặc không hợp lệ')
            row['latitude'] = row['longitude'] = None
        stamp = parse_time(row['timestamp'])
        if stamp is None:
            row['warnings'].append('Timestamp EXIF thiếu hoặc không hợp lệ')
        elif stamp.tzinfo is None:
            row['warnings'].append('Timestamp EXIF chưa rõ múi giờ')
        if info['format'] == 'JPEG':
            row['jpeg_bytes'] = info['file_bytes']
            result = recompress_jpeg(path, quality)
            row['jpeg_recompress_mae'] = result['mae']
            row['jpeg_quality'] = quality
            if not row['jpeg_structure']['structure_ok']:
                raise ValueError('Cấu trúc JPEG lỗi: ' + '; '.join(row['jpeg_structure']['errors'] + row['jpeg_structure']['missing']))
            if row['jpeg_structure']['trailing_bytes']:
                row['warnings'].append('Có dữ liệu sau EOI; không đủ để kết luận giả mạo')
        row['success'] = True
    except Exception as error:
        row['error'] = f'{type(error).__name__}: {error}'
        row['warnings'].append(row['error'])
    finally:
        try:
            row['sha256_after'] = sha256_file(path)
            row['hash_unchanged'] = bool(row['sha256_before']) and row['sha256_before'] == row['sha256_after']
            if not row['hash_unchanged']:
                row['success'] = False
                row['warnings'].append('Hash thay đổi hoặc không thể đối chiếu; cần kiểm tra tập tin')
        except OSError as error:
            row['success'] = False
            row['warnings'].append(f'Không tính được hash sau: {error}')
    return row


def run_batch(paths, quality=90, cancelled=None, progress=None):
    """Hủy giữa hai file, giữ kết quả đã xong; callback không thao tác GUI."""
    started = perf_counter()
    rows = []
    total = len(paths)
    was_cancelled = False
    for path in paths:
        if cancelled is not None and cancelled():
            was_cancelled = True
            break
        rows.append(analyze_file(path, quality))
        if progress is not None:
            progress(len(rows), total)
    return dict(rows=annotate_duplicates(rows), total=total, processed=len(rows),
                succeeded=sum(r['success'] for r in rows), failed=sum(not r['success'] for r in rows),
                cancelled=was_cancelled, elapsed_seconds=perf_counter() - started)


def recheck_hashes(rows, cancelled=None):
    """Đối chiếu hiện trạng với hash ban đầu, không đổi baseline."""
    result = []
    for row in rows:
        if cancelled is not None and cancelled():
            break
        item = dict(row)
        try:
            item['sha256_after'] = sha256_file(row['path'])
            item['hash_unchanged'] = bool(row['sha256_before']) and row['sha256_before'] == item['sha256_after']
            item['hash_check_error'] = ''
        except OSError as error:
            item['sha256_after'] = ''
            item['hash_unchanged'] = False
            item['hash_check_error'] = str(error)
        result.append(item)
    return result
