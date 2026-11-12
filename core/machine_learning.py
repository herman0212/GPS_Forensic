"""Isolation Forest trên đặc trưng ảnh; nhãn ngoại lệ không phải giả mạo."""
from time import perf_counter
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

FEATURES = ['file_bytes', 'width', 'height', 'jpeg_recompress_mae']
SCORE_DESCRIPTION = 'anomaly_score = -score_samples: càng lớn càng khác biệt; decision_function < 0 => Anomaly. Không phải xác suất giả mạo.'


def numeric_feature(value, name):
    """Chỉ nhận số hữu hạn hợp lệ; không biến thiếu dữ liệu thành 0."""
    try:
        if value is None or isinstance(value, bool) or str(value).strip() == '':
            return np.nan
        number = float(value)
        if not np.isfinite(number) or number < 0 or (name in ('width', 'height', 'file_bytes') and number == 0):
            return np.nan
        return number
    except (ValueError, TypeError):
        return np.nan


def prepare_features(records, features=None):
    """Giữ chỉ số dòng để ghép kết quả, không dùng filename/nhãn/GPS làm input."""
    features = list(FEATURES if features is None else features)
    if not features or len(set(features)) != len(features) or any(f not in FEATURES for f in features):
        raise ValueError('Chỉ hỗ trợ các đặc trưng ảnh đã công bố.')
    matrix, indices, excluded = [], [], []
    for index, record in enumerate(records):
        values = [numeric_feature(record.get(name), name) for name in features]
        if record.get('success') is False or all(np.isnan(values)):
            excluded.append(index)
        else:
            matrix.append(values)
            indices.append(index)
    return dict(matrix=np.array(matrix, dtype=float).reshape((-1, len(features))),
                indices=indices, excluded=excluded, features=features)


def train_model(prepared, contamination=0.1):
    """Học trung vị trên tập huấn luyện; bỏ cột hoàn toàn thiếu.

    Không chuẩn hóa: các phép chia ngẫu nhiên theo từng trục của Isolation
    Forest không cần đưa byte, pixel và MAE về cùng đơn vị như mô hình khoảng cách.
    """
    if isinstance(contamination, bool) or not np.isfinite(contamination) or not 0 < contamination <= 0.5:
        raise ValueError('contamination phải lớn hơn 0 và không quá 0.5.')
    matrix = prepared['matrix']
    if len(matrix) < 5:
        raise ValueError('Cần ít nhất 5 ảnh có đặc trưng hợp lệ để huấn luyện.')
    columns = [i for i in range(matrix.shape[1]) if np.isfinite(matrix[:, i]).any()]
    if not columns:
        raise ValueError('Không có cột đặc trưng hợp lệ.')
    matrix = matrix[:, columns].copy()
    medians = np.nanmedian(matrix, axis=0)
    matrix = np.where(np.isnan(matrix), medians, matrix)
    if not np.any(np.ptp(matrix, axis=0) > 0):
        raise ValueError('Các đặc trưng đều giống nhau; không đủ biến thiên để tìm ngoại lệ.')
    model = IsolationForest(n_estimators=100, contamination=float(contamination), random_state=42, n_jobs=1)
    model.fit(matrix)
    return dict(model=model, features=[prepared['features'][i] for i in columns],
                medians=medians, contamination=float(contamination))


def predict_model(trained, records):
    """Dự đoán bằng trung vị của tập train, không học lại từ tập đánh giá."""
    prepared = prepare_features(records, trained['features'])
    rows = [dict(index=i, file=r.get('file', ''), path=r.get('path', ''), label='Excluded',
                 anomaly_score=None, decision_function=None, imputed_features='',
                 reason='Ảnh lỗi hoặc không có đặc trưng số hợp lệ') for i, r in enumerate(records)]
    matrix = prepared['matrix']
    if len(matrix):
        filled = np.where(np.isnan(matrix), trained['medians'], matrix)
        predictions = trained['model'].predict(filled)
        scores = -trained['model'].score_samples(filled)
        decisions = trained['model'].decision_function(filled)
        for position, index in enumerate(prepared['indices']):
            rows[index].update(label='Anomaly' if predictions[position] == -1 else 'Normal',
                               anomaly_score=float(scores[position]), decision_function=float(decisions[position]),
                               imputed_features=', '.join(f for j, f in enumerate(trained['features']) if np.isnan(matrix[position, j])),
                               reason='')
            for j, feature in enumerate(trained['features']):
                rows[index][feature] = float(filled[position, j])
    return rows


def run_isolation_forest(records, contamination=0.1):
    """Phân tích thăm dò trên cùng tập dữ liệu; không tính accuracy giả mạo."""
    started = perf_counter()
    trained = train_model(prepare_features(records), contamination)
    rows = predict_model(trained, records)
    return dict(results=rows, features=trained['features'],
                medians=dict(zip(trained['features'], trained['medians'].tolist())),
                contamination=trained['contamination'], random_state=42,
                normal=sum(r['label'] == 'Normal' for r in rows),
                anomaly=sum(r['label'] == 'Anomaly' for r in rows),
                excluded=sum(r['label'] == 'Excluded' for r in rows),
                elapsed_seconds=perf_counter() - started, score_description=SCORE_DESCRIPTION,
                evaluation='Không có ground truth giả mạo: chỉ báo cáo ngoại lệ và phân bố điểm.')


def evaluate_labels(expected, predicted):
    """Chỉ gọi khi có nhãn thật cho mục tiêu đánh giá; 1 là bất thường."""
    if len(expected) != len(predicted) or not len(expected):
        raise ValueError('Hai dãy nhãn phải cùng độ dài và không rỗng.')
    if any(v not in (0, 1) for v in list(expected) + list(predicted)):
        raise ValueError('Nhãn phải là 0 (bình thường) hoặc 1 (bất thường).')
    return dict(precision=float(precision_score(expected, predicted, zero_division=0)),
                recall=float(recall_score(expected, predicted, zero_division=0)),
                f1=float(f1_score(expected, predicted, zero_division=0)),
                confusion_matrix=confusion_matrix(expected, predicted, labels=[0, 1]).tolist(),
                matrix_order='Hàng: ground truth [0,1]; cột: dự đoán [0,1]')
