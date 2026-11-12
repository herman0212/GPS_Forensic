"""Cấu trúc JPEG và sai khác pixel; không kết luận ảnh giả mạo."""
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps

SOF_CODES = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def inspect_jpeg_structure(path):
    """Đọc segment theo độ dài; sau SOS xử lý byte stuffing và restart.

    JPEG có thể có nhiều scan (progressive). FF00 là byte FF trong entropy,
    FFD0..FFD7 là restart; các marker khác kết thúc vùng entropy hiện tại.
    Đây là kiểm tra cấu trúc cơ bản, không thay cho giải mã Huffman/DCT.
    """
    data = Path(path).read_bytes()
    result = dict(markers=[], missing=[], errors=[], trailing_bytes=0, structure_ok=False)
    if not data.startswith(b'\xff\xd8'):
        result['errors'].append('Không có SOI tại đầu file')
        result['missing'] = ['SOI', 'EOI', 'DQT', 'DHT', 'SOF', 'SOS']
        return result
    result['markers'].append({'name': 'SOI', 'offset': 0})
    position = 2
    entropy = False
    found_eoi = False
    while position < len(data):
        if entropy:
            # Chỉ tìm FF trong vùng entropy, không tìm chuỗi marker toàn file.
            while position < len(data) and data[position] != 0xFF:
                position += 1
            if position >= len(data):
                break
        offset = position
        if data[position] != 0xFF:
            result['errors'].append(f'Thiếu tiền tố FF tại offset {position}')
            break
        while position < len(data) and data[position] == 0xFF:
            position += 1
        if position >= len(data):
            result['errors'].append('File bị cắt trong marker')
            break
        code = data[position]
        position += 1
        if entropy and (code == 0 or 0xD0 <= code <= 0xD7):
            if code:
                result['markers'].append({'name': f'RST{code - 0xD0}', 'offset': offset})
            continue
        was_entropy = entropy
        entropy = False
        name = {0xD8: 'SOI', 0xD9: 'EOI', 0xDB: 'DQT', 0xC4: 'DHT', 0xDA: 'SOS'}.get(code, f'FF{code:02X}')
        if code in SOF_CODES:
            name = 'SOF'
        result['markers'].append({'name': name, 'offset': offset})
        if code == 0xD9:
            found_eoi = True
            result['trailing_bytes'] = len(data) - position
            break
        if code == 0xD8 or code == 0 or 0xD0 <= code <= 0xD7:
            result['errors'].append(f'Marker {name} không hợp lệ ngoài entropy tại {offset}')
            break
        if code == 0x01:  # TEM không có độ dài segment.
            entropy = was_entropy
            continue
        if code < 0xC0:
            result['errors'].append(f'Mã marker dành riêng chưa hỗ trợ: FF{code:02X}')
            break
        if position + 2 > len(data):
            result['errors'].append('File bị cắt trước độ dài segment')
            break
        length = int.from_bytes(data[position:position + 2], 'big')
        if length < 2:
            result['errors'].append(f'Độ dài segment không hợp lệ tại {offset}')
            break
        if position + length > len(data):
            result['errors'].append(f'Segment tại {offset} vượt cuối file (bị cắt)')
            break
        if code == 0xDA:
            if length < 6 or data[position + 2] == 0 or length != 6 + 2 * data[position + 2]:
                result['errors'].append('Header SOS không hợp lệ')
                break
            entropy = True
        if code in SOF_CODES:
            if length < 8 or data[position + 7] == 0 or length != 8 + 3 * data[position + 7]:
                result['errors'].append('Header SOF không hợp lệ')
                break
        if code == 0xDC and was_entropy:  # DNL có thể nằm trong một scan.
            entropy = True
        position += length
    names = {m['name'] for m in result['markers']}
    result['missing'] = [name for name in ('SOI', 'EOI', 'DQT', 'DHT', 'SOF', 'SOS') if name not in names]
    if not found_eoi:
        result['errors'].append('Thiếu EOI; file có thể bị cắt')
    # Một số kiểu JPEG không dùng DHT hoặc DQT; báo thiếu riêng, không tự kết
    # luận lỗi chỉ từ hai marker này. Pillow kiểm tra khả năng giải mã độc lập.
    result['structure_ok'] = not result['errors'] and not {'SOI', 'EOI', 'SOF', 'SOS'}.intersection(result['missing'])
    return result


def pixel_mae(first, second):
    """MAE = tổng |a-b| / số thành phần pixel; không resize để ép cùng cỡ."""
    a, b = np.asarray(first), np.asarray(second)
    if a.shape != b.shape or a.size == 0:
        raise ValueError('Hai mảng pixel phải cùng kích thước và không rỗng.')
    # Chuyển float trước phép trừ để tránh tràn số uint8.
    return float(np.abs(a.astype(np.float64) - b.astype(np.float64)).mean())


def recompress_jpeg(path, quality=90):
    """Tái nén trong RAM; trả MAE, ảnh sai khác và histogram 256 mức."""
    if not isinstance(quality, int) or not 1 <= quality <= 100:
        raise ValueError('Chất lượng JPEG phải là số nguyên từ 1 đến 100.')
    with Image.open(path) as image:
        if image.format != 'JPEG':
            raise ValueError('Tái nén JPEG chỉ áp dụng cho định dạng thực tế JPEG.')
        original = image.convert('RGB')
    buffer = io.BytesIO()
    original.save(buffer, format='JPEG', quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as image:
        compressed = image.convert('RGB')
    a, b = np.asarray(original), np.asarray(compressed)
    difference = np.abs(a.astype(np.int16) - b.astype(np.int16)).astype(np.uint8)
    histogram = np.bincount(difference.ravel(), minlength=256).tolist()
    diff_image = Image.fromarray(difference)
    return dict(mae=pixel_mae(a, b), quality=quality, difference=diff_image,
                difference_display=ImageOps.autocontrast(diff_image), histogram=histogram)


def image_information(path):
    """Định dạng thực tế do Pillow nhận diện, không dựa phần mở rộng."""
    path = Path(path)
    with Image.open(path) as image:
        image.load()
        result = dict(file=path.name, path=str(path), format=image.format,
                      width=image.width, height=image.height, mode=image.mode,
                      file_bytes=path.stat().st_size)
        if image.format == 'JPEG':
            result['jpeg_info'] = dict(progressive=bool(image.info.get('progressive') or image.info.get('progression')),
                                       quantization_tables=getattr(image, 'quantization', {}),
                                       component_sampling=getattr(image, 'layer', []))
    return result


def compare_images(first_path, second_path):
    """Hash so byte; MAE so RGB đã giải mã, chỉ khi cùng kích thước."""
    from core.integrity import sha256_file
    first, second = image_information(first_path), image_information(second_path)
    first['sha256'] = sha256_file(first_path)
    second['sha256'] = sha256_file(second_path)
    result = dict(first=first, second=second, same_bytes=first['sha256'] == second['sha256'],
                  pixel_mae=None, reason='')
    if (first['width'], first['height']) != (second['width'], second['height']):
        result['reason'] = 'Khác kích thước; không resize để tính MAE.'
        return result
    with Image.open(first_path) as a, Image.open(second_path) as b:
        result['pixel_mae'] = pixel_mae(a.convert('RGB'), b.convert('RGB'))
    return result
