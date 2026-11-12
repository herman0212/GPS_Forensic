"""SHA-256 đọc theo khối và phân biệt trùng nội dung/trùng tên."""
import hashlib
from collections import Counter
from pathlib import Path


def sha256_file(path):
    """Không nạp toàn bộ tập tin vào RAM khi tính hash."""
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def annotate_duplicates(rows):
    """Trả bản sao có số file trùng byte và số tên trùng; bỏ hash rỗng."""
    hashes = Counter(r.get('sha256_before') for r in rows if r.get('sha256_before'))
    names = Counter(r['file'].casefold() for r in rows)
    result = []
    for row in rows:
        item = dict(row)
        item['same_content_count'] = hashes.get(row.get('sha256_before'), 0)
        item['same_name_count'] = names[row['file'].casefold()]
        result.append(item)
    return result
