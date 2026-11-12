"""Kiểm thử ML và metric trên dữ liệu nhỏ có kết quả kiểm chứng được."""
from copy import deepcopy
import csv
import numpy as np
import pytest
from core.machine_learning import (FEATURES, prepare_features, train_model, predict_model,
                                    run_isolation_forest, evaluate_labels)
from core.metadata import export_rows
from core.experiments import controlled_experiment


def sample_records(count=20):
    return [dict(file=f'{i}.jpg', path=f'{i}.jpg', file_bytes=1000 + i * 10,
                 width=640 + i, height=480, jpeg_recompress_mae=1 + i / 100,
                 timestamp=f'2025-01-01T00:{i:02d}:00', latitude=10, longitude=106)
            for i in range(count)]


def test_features_exclude_names_labels_and_gps():
    records = sample_records()
    records[0].update(label='Anomaly', latitude=181, speed_kmh=99999)
    prepared = prepare_features(records)
    assert prepared['features'] == FEATURES
    assert prepared['matrix'].shape == (20, 4)
    with pytest.raises(ValueError):
        prepare_features(records, ['latitude'])


def test_missing_values_train_median_and_empty_columns():
    records = sample_records()
    records[0]['file_bytes'] = None
    for row in records:
        row['jpeg_recompress_mae'] = None
    trained = train_model(prepare_features(records))
    assert 'jpeg_recompress_mae' not in trained['features']
    test = [dict(file='new', width=700, height=480, file_bytes=None)]
    result = predict_model(trained, test)[0]
    assert result['file_bytes'] == np.median([r['file_bytes'] for r in records[1:]])
    assert 'file_bytes' in result['imputed_features']
    assert result['file_bytes'] != 0


def test_failed_and_all_missing_are_excluded():
    records = sample_records()
    records += [dict(file='empty'), dict(file='failed', success=False, file_bytes=999)]
    result = run_isolation_forest(records)
    assert result['excluded'] == 2
    assert result['results'][-1]['anomaly_score'] is None


@pytest.mark.parametrize('contamination', [0, -0.1, 0.51, float('nan'), True])
def test_invalid_contamination(contamination):
    with pytest.raises(ValueError):
        run_isolation_forest(sample_records(), contamination)


def test_insufficient_and_constant_data():
    with pytest.raises(ValueError):
        run_isolation_forest(sample_records(4))
    with pytest.raises(ValueError):
        run_isolation_forest([dict(file=str(i), width=100) for i in range(6)])


def test_scores_and_repeatability_do_not_mutate_input():
    records = sample_records()
    before = deepcopy(records)
    one = run_isolation_forest(records, 0.2)
    two = run_isolation_forest(records, 0.2)
    assert one['normal'] + one['anomaly'] == 20
    assert one['anomaly'] == 4
    assert one['results'] == two['results']
    assert all(np.isfinite(r['anomaly_score']) for r in one['results'])
    assert all((r['label'] == 'Anomaly') == (r['decision_function'] < 0) for r in one['results'])
    assert records == before


def test_precision_recall_f1_and_confusion():
    metrics = evaluate_labels([0, 0, 1, 1], [0, 1, 0, 1])
    assert metrics['precision'] == metrics['recall'] == metrics['f1'] == 0.5
    assert metrics['confusion_matrix'] == [[1, 1], [1, 1]]
    with pytest.raises(ValueError):
        evaluate_labels([], [])


def test_ml_csv(tmp_path):
    path = tmp_path / 'ml.csv'
    export_rows(run_isolation_forest(sample_records())['results'], path)
    with path.open(encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 20
    assert 'anomaly_score' in rows[0]


def test_controlled_data_is_copy_and_labels_are_not_authenticity():
    records = sample_records()
    before = deepcopy(records)
    result = controlled_experiment(records)
    assert records == before
    assert result['real_ground_truth_metrics'] is None
    assert result['numeric_injected_indices'] == [17, 18, 19]
    assert result['metadata_metrics']['recall'] == 1
