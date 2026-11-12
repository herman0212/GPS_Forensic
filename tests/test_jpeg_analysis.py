"""JPEG tạo trong thư mục tạm, gồm progressive và marker giả trong payload."""
import numpy as np
import pytest
from PIL import Image
from core.integrity import sha256_file
from core.jpeg_analysis import (inspect_jpeg_structure, recompress_jpeg, pixel_mae,
                                compare_images, image_information)


def make_jpeg(path, progressive=False):
    data = np.arange(32 * 48 * 3, dtype=np.uint8).reshape(32, 48, 3)
    Image.fromarray(data).save(path, quality=94, progressive=progressive)
    return path


@pytest.mark.parametrize('progressive', [False, True])
def test_valid_jpeg(tmp_path, progressive):
    path = make_jpeg(tmp_path / 'image.jpg', progressive)
    result = inspect_jpeg_structure(path)
    assert result['structure_ok']
    assert result['missing'] == result['errors'] == []
    assert result['trailing_bytes'] == 0


def test_truncated_and_trailing(tmp_path):
    path = make_jpeg(tmp_path / 'image.jpg')
    original = path.read_bytes()
    cut = tmp_path / 'cut.jpg'
    cut.write_bytes(original[:-12])
    assert not inspect_jpeg_structure(cut)['structure_ok']
    assert 'EOI' in inspect_jpeg_structure(cut)['missing']
    extra = tmp_path / 'extra.jpg'
    extra.write_bytes(original + b'extra data')
    result = inspect_jpeg_structure(extra)
    assert result['structure_ok']
    assert result['trailing_bytes'] == 10


def test_segment_lengths_and_entropy(tmp_path):
    # EOI giả nằm trong APP và FF00 D9 trong entropy không kết thúc JPEG.
    soi = b'\xff\xd8'
    app = b'\xff\xe1\x00\x06xx\xff\xd9'
    sof = b'\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00'
    sos = b'\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00'
    path = tmp_path / 'structure.jpg'
    path.write_bytes(soi + app + sof + sos + b'abc\xff\x00\xd9\xff\xd0xyz\xff\xd9TAIL')
    result = inspect_jpeg_structure(path)
    assert result['structure_ok']
    assert result['trailing_bytes'] == 4
    assert sum(m['name'] == 'EOI' for m in result['markers']) == 1
    assert any(m['name'] == 'RST0' for m in result['markers'])
    assert 'DQT' in result['missing'] and 'DHT' in result['missing']


@pytest.mark.parametrize('data', [b'', b'not jpeg', b'\xff\xd8\xff', b'\xff\xd8\xff\xdb\x00\x01',
                                   b'\xff\xd8\xff\xdb\xff\xffxx', b'\xff\xd8\xff\xd9'])
def test_invalid_structures(tmp_path, data):
    path = tmp_path / 'bad.jpg'
    path.write_bytes(data)
    assert not inspect_jpeg_structure(path)['structure_ok']


def test_recompression_preserves_hash_and_histogram(tmp_path):
    path = make_jpeg(tmp_path / 'image.jpg')
    before = sha256_file(path)
    result = recompress_jpeg(path)
    assert result['quality'] == 90
    assert result['mae'] >= 0
    assert result['difference'].size == (48, 32)
    assert sum(result['histogram']) == 48 * 32 * 3
    assert result['mae'] == pytest.approx(sum(i * n for i, n in enumerate(result['histogram'])) / (48 * 32 * 3))
    assert sha256_file(path) == before


def test_quality_changes_result(tmp_path):
    path = make_jpeg(tmp_path / 'image.jpg')
    assert recompress_jpeg(path, 20)['mae'] > recompress_jpeg(path, 95)['mae']
    with pytest.raises(ValueError):
        recompress_jpeg(path, 0)


def test_pixel_mae_zero_and_unsigned():
    a = np.array([0, 255], dtype=np.uint8)
    assert pixel_mae(a, a) == 0
    assert pixel_mae(a, np.array([255, 0], dtype=np.uint8)) == 255
    with pytest.raises(ValueError):
        pixel_mae(np.zeros((3, 3)), np.zeros((2, 2)))


def test_compare_bytes_and_pixels(tmp_path):
    a, b = tmp_path / 'a.png', tmp_path / 'b.bmp'
    Image.new('RGB', (12, 10), 'red').save(a)
    Image.new('RGB', (12, 10), 'red').save(b)
    result = compare_images(a, b)
    assert not result['same_bytes']
    assert result['pixel_mae'] == 0
    Image.new('RGB', (13, 10), 'red').save(b)
    assert compare_images(a, b)['pixel_mae'] is None


def test_actual_format_not_extension(tmp_path):
    path = tmp_path / 'fake.jpg'
    Image.new('RGB', (12, 12)).save(path, format='PNG')
    assert image_information(path)['format'] == 'PNG'
    with pytest.raises(ValueError):
        recompress_jpeg(path)
