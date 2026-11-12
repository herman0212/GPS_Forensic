"""Batch, hash và hủy an toàn trên dữ liệu tạm."""
import hashlib
import shutil
from PIL import Image
from core.integrity import sha256_file
from core.batch import list_images, run_batch, analyze_file, recheck_hashes


def test_known_sha256_and_multiblock(tmp_path):
    path = tmp_path / 'sample'
    path.write_bytes(b'abc')
    assert sha256_file(path) == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    data = b'x' * (2 * 1024 * 1024 + 17)
    path.write_bytes(data)
    assert sha256_file(path) == hashlib.sha256(data).hexdigest()


def test_empty_folder(tmp_path):
    result = run_batch(list_images(tmp_path))
    assert result['total'] == result['processed'] == result['failed'] == 0
    assert not result['cancelled']


def test_formats_recursion_and_bad_image(tmp_path):
    nested = tmp_path / 'sub'
    nested.mkdir()
    for name in ['a.jpg', 'b.JPEG', 'c.png', 'd.tiff']:
        Image.new('RGB', (20, 20)).save(tmp_path / name)
    Image.new('RGB', (20, 20)).save(nested / 'inside.tif')
    (tmp_path / 'bad.jpg').write_bytes(b'not an image')
    assert len(list_images(tmp_path)) == 5
    assert len(list_images(tmp_path, True)) == 6
    progress = []
    result = run_batch(list_images(tmp_path, True), progress=lambda done, total: progress.append((done, total)))
    assert result['succeeded'] == 5 and result['failed'] == 1
    assert progress[-1] == (6, 6)
    assert all(r['hash_unchanged'] for r in result['rows'])


def test_duplicates_distinguish_names_and_bytes(tmp_path):
    sub = tmp_path / 'sub'
    sub.mkdir()
    Image.new('RGB', (20, 20), 'red').save(tmp_path / 'a.png')
    shutil.copyfile(tmp_path / 'a.png', tmp_path / 'copy.png')
    Image.new('RGB', (20, 20), 'blue').save(sub / 'a.png')
    result = run_batch(list_images(tmp_path, True))
    rows = {r['path']: r for r in result['rows']}
    first = rows[str((tmp_path / 'a.png').resolve())]
    other = rows[str((sub / 'a.png').resolve())]
    assert first['same_content_count'] == 2 and first['same_name_count'] == 2
    assert other['same_content_count'] == 1 and other['same_name_count'] == 2
    assert first['sha256_before'] != other['sha256_before']


def test_cancel_preserves_files_and_partial_results(tmp_path):
    for i in range(4):
        Image.new('RGB', (20, 20)).save(tmp_path / f'{i}.jpg')
    paths = list_images(tmp_path)
    hashes = {p: sha256_file(p) for p in paths}
    done = []
    result = run_batch(paths, cancelled=lambda: len(done) >= 1, progress=lambda a, b: done.append(a))
    assert result['cancelled'] and result['processed'] == 1
    assert all(sha256_file(p) == value for p, value in hashes.items())
    assert run_batch(paths, cancelled=lambda: True)['processed'] == 0


def test_recheck_detects_changes_without_replacing_baseline(tmp_path):
    path = tmp_path / 'image.png'
    Image.new('RGB', (20, 20), 'red').save(path)
    row = analyze_file(path)
    original = row['sha256_before']
    Image.new('RGB', (20, 20), 'blue').save(path)
    changed = recheck_hashes([row])[0]
    assert not changed['hash_unchanged']
    assert changed['sha256_before'] == original
    assert row['hash_unchanged'] is True
    path.unlink()
    assert recheck_hashes([row])[0]['hash_check_error']


def test_missing_and_truncated_file_do_not_stop_batch(tmp_path):
    path = tmp_path / 'truncated.jpg'
    Image.new('RGB', (20, 20)).save(path)
    path.write_bytes(path.read_bytes()[:-8])
    result = run_batch([tmp_path / 'missing.jpg', path])
    assert result['failed'] == 2
    assert result['rows'][1]['jpeg_structure']['structure_ok'] is False


def test_trailing_jpeg_is_warning_not_failure(tmp_path):
    path = tmp_path / 'trailing.jpg'
    Image.new('RGB', (20, 20)).save(path)
    with path.open('ab') as stream:
        stream.write(b'additional data')
    row = analyze_file(path)
    assert row['success']
    assert row['jpeg_structure']['trailing_bytes'] == 15
    assert row['warnings']
