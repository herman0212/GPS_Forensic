"""Bổ sung đặc trưng ảnh thật vào bản sao metadata và theo dõi bộ dữ liệu."""
import hashlib
import json
from copy import deepcopy
from core.batch import analyze_file
from core.machine_learning import FEATURES, numeric_feature
import numpy as np

IMAGE_FIELDS = ['file_bytes', 'width', 'height', 'mode', 'format', 'size', 'jpeg_info',
                'jpeg_structure', 'jpeg_recompress_mae', 'jpeg_quality', 'jpeg_bytes',
                'sha256_before', 'sha256_after', 'hash_unchanged', 'success', 'error', 'exif']


def dataset_signature(records):
    """Dấu vân tay trạng thái trong RAM để không dùng nhầm ML sau khi đổi bộ ảnh."""
    data = json.dumps(records, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def collect_features(records, progress=None, cancelled=None):
    """Tái sử dụng kết quả Batch nếu có, đọc ảnh thiếu đặc trưng trên luồng nền.

    Chỉ ghép thông tin ảnh tính được; không ghi đè timestamp/GPS nguồn CSV.
    """
    enriched = deepcopy(records)
    for index, row in enumerate(enriched):
        if cancelled is not None and cancelled():
            raise ValueError('Đã hủy trước khi hoàn tất đặc trưng; không huấn luyện trên tập dở dang.')
        ready = all(np.isfinite(numeric_feature(row.get(f), f)) for f in FEATURES[:3])
        if row.get('format') == 'JPEG' and not np.isfinite(numeric_feature(row.get('jpeg_recompress_mae'), 'jpeg_recompress_mae')):
            ready = False
        if not ready and row.get('path'):
            analysis = analyze_file(row['path'])
            for field in IMAGE_FIELDS:
                if field in analysis:
                    row[field] = analysis[field]
            row['image_analysis_warnings'] = analysis['warnings']
        if progress is not None:
            progress(index + 1, len(enriched))
    return enriched
