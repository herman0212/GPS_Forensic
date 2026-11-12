"""Thực nghiệm 100 ảnh và lưu minh chứng Giai đoạn 4, chỉ đọc nguồn."""
import json
import sys
from pathlib import Path
from time import perf_counter
from collections import Counter
from core.metadata import load_dataset, export_rows
from core.integrity import sha256_file
from core.stage4_analysis import collect_features
from core.machine_learning import run_isolation_forest
from core.experiments import controlled_experiment
from core.reporting import build_report, export_pdf


def write_summary(output, summary, experiment):
    """Ghi diễn giải từ số đo thật, không chèn metric cho ground truth thiếu."""
    numeric = experiment['numeric_metrics']
    metadata = experiment['metadata_metrics']
    text = f'''# Thực nghiệm Giai đoạn 4

## Dữ liệu thật

- 100 ảnh Image2GPS-25, metadata CSV riêng; không có EXIF gốc, thời gian chưa rõ múi giờ.
- Đặc trưng: file_bytes, width, height, jpeg_recompress_mae.
- Isolation Forest: 100 cây, contamination=0.1, random_state=42; không dùng GPS/thời gian/vận tốc.
- Normal: {summary['normal']}; Anomaly: {summary['anomaly']}; Excluded: {summary['excluded']}.
- Không có ground truth giả mạo: không tính Precision/Recall/F1/confusion matrix thật/giả trên dataset gốc.
- Luật: 100 thông tin chưa rõ múi giờ; 14 bản ghi timestamp trùng. Đây không phải nhãn giả mạo.

## Thời gian và toàn vẹn

- Tính đặc trưng ảnh thật: {summary['feature_seconds']:.3f} giây.
- ML sau khi có đặc trưng: {summary['ml_seconds']:.3f} giây.
- Xuất PDF: {summary['pdf_seconds']:.3f} giây.
- Toàn bộ thực nghiệm, gồm kiểm tra hash và xuất minh chứng: {summary['total_seconds']:.3f} giây.
- {summary['protected_files']} file được đối chiếu; hash giữ nguyên: {summary['all_protected_hashes_unchanged']}.
- Hash trước/sau phân tích của mọi ảnh giữ nguyên: {summary['all_image_analysis_hashes_unchanged']}.
- chapter3_evidence tồn tại khi chạy: {summary['chapter3_evidence_present']}. Không tạo, sửa hoặc xóa thư mục này.
- 105 file được bảo vệ tại lần chạy này: 100 ảnh + metadata.csv + 4 file outputs/stage3_*.

## Can thiệp tổng hợp có kiểm soát

Mọi can thiệp chỉ trên deepcopy của metadata/đặc trưng, không sửa file gốc. Không điều chỉnh contamination theo kết quả. Mô hình học tập gốc rồi dự đoán bản sao; đây không phải đánh giá độc lập về giả mạo.

- Ba lỗi metadata: GPS ngoài phạm vi, timestamp sai, timestamp thiếu. Metric chỉ cho nhãn lỗi metadata được chèn: precision={metadata['precision']:.3f}, recall={metadata['recall']:.3f}, F1={metadata['f1']:.3f}; confusion matrix={metadata['confusion_matrix']}.
- Ba dòng đặc trưng số tăng hệ số 30/40/50. Metric chỉ cho nhãn can thiệp số được chèn: precision={numeric['precision']:.3f}, recall={numeric['recall']:.3f}, F1={numeric['f1']:.3f}; confusion matrix={numeric['confusion_matrix']}.
- Thứ tự ma trận: hàng ground truth [0,1], cột dự đoán [0,1]. Nhãn 1 là can thiệp đã biết, không phải giả mạo.
- ML nhận ra 3/3 dòng can thiệp nhưng đánh dấu thêm 10 dòng không can thiệp. Đây là giới hạn thực tế cần trình bày, không được giấu hoặc dùng để điều chỉnh tham số rồi nhận là đánh giá độc lập.

## So sánh phương pháp

| Phương pháp | Đầu vào/mục đích | Ưu điểm | Giới hạn |
|---|---|---|---|
| Quy tắc | GPS, timestamp, nguồn; tính hợp lệ/nhất quán | Nêu rõ lỗi và ngưỡng | Chỉ lỗi đã mô tả, phụ thuộc metadata |
| Isolation Forest | Đặc trưng ảnh; ngoại lệ thống kê | Không cần nhãn giả mạo khi fit | Phụ thuộc tập ảnh/contamination; không xác nhận nguyên nhân hay giả mạo |

## Minh chứng và kiểm tra

- ml_results.csv: kết quả thật từng ảnh, điểm và giá trị đặc trưng sau điền trung vị nếu cần.
- evaluation.json: số liệu thật và tổng hợp tách riêng; metric thật/giả là null.
- report_snapshot.json và geoimage_forensics_report.pdf: báo cáo thao tác thực tế, không phải báo cáo nghiên cứu hoàn chỉnh.
- protected_manifest_before.json / protected_manifest_after.json: hash đối chiếu của nguồn và minh chứng cũ.
- pytest_results.txt: log pytest cuối, gồm toàn bộ 62 bài hồi quy và bài mới.
- gui_ml.png: giao diện trên dữ liệu thật; pdf_preview/: mọi trang PDF đã render để kiểm tra bố cục và Unicode.

## File mã nguồn

Tạo: core/machine_learning.py, core/stage4_analysis.py, core/experiments.py, core/reporting.py, gui/stage4_tabs.py, tests/test_machine_learning.py, tests/test_reporting.py, tests/test_gui_stage4.py, tests/experiment_stage4.py.

Sửa: gui/main_window.py, requirements.txt, README.md, HUONG_DAN_CODE.md. Các file kiểm thử Giai đoạn 1–3 không bị sửa/bỏ qua.

## Chạy lại

```powershell
.\\.venv\\Scripts\\python.exe main.py
.\\.venv\\Scripts\\python.exe -m pytest -v
.\\.venv\\Scripts\\python.exe -m tests.experiment_stage4
```

Lưu ý: mô hình là thăm dò; GUI offscreen không kiểm tra bản đồ nền trực tuyến. Chưa có chế độ ML GPS/thời gian. PDF/fit không bị ngắt cưỡng bức giữa tác vụ. Không có nhãn giả mạo hợp lệ nên không đánh giá khả năng xác thực ảnh.
'''
    (output / 'experiment_summary.md').write_text(text, encoding='utf-8')


def main():
    # Console Windows có thể mặc định cp1252, không đủ ký tự tiếng Việt.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    root = Path.cwd()
    output = root / 'outputs/stage4'
    output.mkdir(parents=True, exist_ok=True)
    protected = sorted(p for p in (root / 'data').rglob('*') if p.is_file())
    protected += sorted((root / 'outputs').glob('stage3_*'))
    evidence = root / 'outputs/chapter3_evidence'
    if evidence.is_dir():
        protected += sorted(p for p in evidence.rglob('*') if p.is_file())
    before = {str(p.relative_to(root)): sha256_file(p) for p in protected}
    (output / 'protected_manifest_before.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    started = perf_counter()
    records = load_dataset(root / 'data/Image2GPS25/metadata.csv')
    features_started = perf_counter()
    enriched = collect_features(records, progress=lambda done, total: print(f'Đặc trưng {done}/{total}', flush=True) if done % 10 == 0 else None)
    feature_seconds = perf_counter() - features_started
    ml = run_isolation_forest(enriched, 0.1)
    experiment = controlled_experiment(enriched, 0.1)
    export_rows(ml['results'], output / 'ml_results.csv')
    export_rows(experiment['numeric_predictions'], output / 'controlled_numeric_predictions.csv')
    export_rows(experiment['metadata_alerts'], output / 'controlled_metadata_alerts.csv')
    (output / 'features_records.json').write_text(json.dumps(enriched, indent=2, ensure_ascii=False), encoding='utf-8')
    report = build_report(enriched, ml, 'Image2GPS-25: 100 JPEG chuyển đổi bằng Pillow; metadata CSV riêng; không có EXIF gốc; timestamp không offset.')
    (output / 'report_snapshot.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    pdf_started = perf_counter()
    export_pdf(report, output / 'geoimage_forensics_report.pdf')
    pdf_seconds = perf_counter() - pdf_started
    experiment['real_dataset'] = dict(total=len(enriched), normal=ml['normal'], anomaly=ml['anomaly'], excluded=ml['excluded'],
                                     features=ml['features'], contamination=0.1,
                                     score_min=min(r['anomaly_score'] for r in ml['results'] if r['anomaly_score'] is not None),
                                     score_max=max(r['anomaly_score'] for r in ml['results'] if r['anomaly_score'] is not None),
                                     ground_truth=None, precision=None, recall=None, f1=None, confusion_matrix=None)
    (output / 'evaluation.json').write_text(json.dumps(experiment, indent=2, ensure_ascii=False), encoding='utf-8')
    after = {str(p.relative_to(root)): sha256_file(p) for p in protected}
    unchanged = before == after
    (output / 'protected_manifest_after.json').write_text(json.dumps(after, indent=2), encoding='utf-8')
    summary = dict(total=len(enriched), normal=ml['normal'], anomaly=ml['anomaly'], excluded=ml['excluded'],
                   feature_seconds=feature_seconds, ml_seconds=ml['elapsed_seconds'], pdf_seconds=pdf_seconds,
                   total_seconds=perf_counter() - started, protected_files=len(before),
                   all_protected_hashes_unchanged=unchanged, chapter3_evidence_present=evidence.is_dir(),
                   all_image_analysis_hashes_unchanged=all(r.get('hash_unchanged') for r in enriched),
                   rules=dict(Counter(a['kind'] for a in report['alerts'])))
    (output / 'timing_and_integrity.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    write_summary(output, summary, experiment)
    print(json.dumps(summary, indent=2, ensure_ascii=False), flush=True)
    assert len(enriched) == 100 and unchanged and summary['all_image_analysis_hashes_unchanged']


if __name__ == '__main__':
    main()
