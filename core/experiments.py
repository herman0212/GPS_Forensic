"""Thực nghiệm trên bản sao dữ liệu; không gán nhãn giả mạo cho ảnh gốc."""
from copy import deepcopy
from core.machine_learning import FEATURES, prepare_features, train_model, predict_model, evaluate_labels
from core.anomaly import analyze_rules


def controlled_experiment(records, contamination=0.1):
    """Giữ tham số cố định; nhãn chỉ mô tả can thiệp tổng hợp đã biết.

    Mô hình học tập gốc rồi áp dụng trên bản sao. Đây là kiểm tra phản ứng với
    dữ liệu tổng hợp, không phải đánh giá độc lập khả năng phát hiện giả mạo.
    """
    if len(records) < 10:
        raise ValueError('Cần ít nhất 10 bản ghi cho thí nghiệm có kiểm soát.')
    trained = train_model(prepare_features(records), contamination)
    numeric = deepcopy(records)
    injected = list(range(len(records) - 3, len(records)))
    for feature in FEATURES:
        values = [float(r[feature]) for r in records if r.get(feature) is not None]
        if values:
            for order, index in enumerate(injected):
                numeric[index][feature] = max(max(values), 1) * (30 + order * 10)
    predicted = predict_model(trained, numeric)
    expected = [int(i in injected) for i in range(len(records))]
    if any(r['label'] == 'Excluded' for r in predicted):
        numeric_metrics = {'status': 'Có dòng không dự đoán được; không tính metric trên tập thiếu.'}
    else:
        numeric_metrics = evaluate_labels(expected, [int(r['label'] == 'Anomaly') for r in predicted])
    metadata = deepcopy(records)
    metadata[0]['latitude'] = 181
    if 'csv_original' in metadata[0]:
        metadata[0]['csv_original']['lat'] = '181'
    metadata[1]['timestamp'] = 'not-a-timestamp'
    metadata[2]['timestamp'] = ''
    alerts = analyze_rules(metadata)['alerts']
    bad_kinds = {'gps_invalid', 'gps_missing', 'time_invalid', 'time_missing'}
    detected = {a['file'] for a in alerts if a['kind'] in bad_kinds and a['level'] != 'Thông tin'}
    metadata_metrics = evaluate_labels([int(i < 3) for i in range(len(records))],
                                       [int(r['file'] in detected) for r in metadata])
    return dict(scope='Nhãn can thiệp tổng hợp, KHÔNG phải nhãn ảnh thật/giả mạo. Không phải đánh giá độc lập.',
                contamination=contamination, numeric_injected_indices=injected,
                numeric_metrics=numeric_metrics, numeric_predictions=predicted,
                metadata_injected_indices=[0, 1, 2], metadata_metrics=metadata_metrics,
                metadata_alerts=alerts,
                real_ground_truth_metrics=None,
                comparison=[
                    dict(method='Quy tắc', purpose='Kiểm tra tính hợp lệ/nhất quán metadata',
                         inputs='GPS, timestamp và nguồn CSV/EXIF', advantages='Giải thích được bằng luật và ngưỡng',
                         limitations='Chỉ phát hiện lỗi đã mô tả; phụ thuộc chất lượng metadata'),
                    dict(method='Isolation Forest', purpose='Tìm ngoại lệ thống kê tương đối trong đặc trưng ảnh',
                         inputs=', '.join(trained['features']), advantages='Không cần nhãn giả mạo để huấn luyện',
                         limitations='Phụ thuộc tập ảnh/contamination; điểm không giải thích nguyên nhân hay chứng minh chỉnh sửa')])
