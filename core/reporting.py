"""Báo cáo thao tác phân tích, phân biệt nguồn gốc và kết quả suy luận."""
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from core.anomaly import analyze_rules
from core.gps import valid_gps
from core.timeline import parse_time, time_key

PROJECT_TITLE = 'NGHIÊN CỨU KỸ THUẬT IMAGE FORENSICS VÀ XÂY DỰNG CHƯƠNG TRÌNH BẰNG PYTHON HỖ TRỢ PHÂN TÍCH ẢNH SỐ'
LIMITATIONS = ('CSV không phải EXIF nhúng trong ảnh. Timestamp thiếu offset không được tự gán múi giờ. '
               'SHA-256 xác minh byte tại thời điểm đo, không chứng minh nguồn gốc chụp. '
               'JPEG MAE, dữ liệu sau EOI, GPS và Isolation Forest không đủ để kết luận giả mạo. '
               'Ngoại lệ thống kê khác với bất thường metadata và khác với ảnh bị chỉnh sửa. '
               'Không có nhãn ground truth giả mạo đáng tin cậy thì không tính Precision/Recall/F1 cho ảnh thật/giả. '
               'Thực nghiệm tổng hợp chỉ kiểm tra phản ứng với can thiệp đã biết, không phải đánh giá độc lập.')


def protect_output(path, records=()):
    """Không ghi báo cáo lên dữ liệu gốc hoặc minh chứng Giai đoạn 3."""
    target = Path(path).resolve()
    root = Path(__file__).resolve().parents[1]
    if target.is_relative_to(root / 'data') or target.is_relative_to(root / 'outputs/chapter3_evidence') or target.name.startswith('stage3_'):
        raise ValueError('Không được ghi lên dữ liệu gốc hoặc minh chứng Giai đoạn 3.')
    for record in records:
        for key in ('path', 'csv_source'):
            if record.get(key) and target == Path(record[key]).resolve():
                raise ValueError('Đường dẫn đầu ra trùng với tập tin nguồn.')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def build_report(records, ml=None, dataset='Bộ ảnh đang phân tích', rule_options=None):
    """Chụp kết quả đã có, không tự điền kết quả JPEG/hash chưa đo."""
    records = deepcopy(records)
    alerts, pairs = analyze_rules(records, **(rule_options or {}))
    times = [parse_time(r.get('timestamp')) for r in records]
    time_counts = Counter(time_key(t) for t in times if t)
    measured_hashes = [r for r in records if r.get('sha256_before') and r.get('sha256_after')]
    maes = [r['jpeg_recompress_mae'] for r in records if r.get('jpeg_recompress_mae') is not None]
    if ml is not None:
        if len(ml['results']) != len(records) or any(m['file'] != r['file'] or m.get('path', '') != r.get('path', '') for m, r in zip(ml['results'], records)):
            raise ValueError('Kết quả ML không thuộc bộ ảnh hiện tại.')
    return dict(title=PROJECT_TITLE, analyzed_at=datetime.now(timezone(timedelta(hours=7))).isoformat(),
                clock_note='Thời điểm lập báo cáo UTC+07:00, không phải timezone suy đoán của ảnh.',
                dataset=dataset, total=len(records),
                metadata=dict(csv=sum('csv_original' in r for r in records),
                              exif_present=sum(bool(r.get('exif', {}).get('tags')) for r in records)),
                gps=dict(valid=sum(valid_gps(r.get('latitude'), r.get('longitude')) for r in records)),
                timeline=dict(valid=sum(t is not None for t in times),
                              missing=sum(not str(r.get('timestamp') or '').strip() for r in records),
                              invalid=sum(t is None and bool(str(r.get('timestamp') or '').strip()) for r, t in zip(records, times)),
                              unknown_timezone=sum(t is not None and t.tzinfo is None for t in times),
                              duplicate_records=sum(count for count in time_counts.values() if count > 1)),
                integrity=dict(measured=len(measured_hashes), unchanged=sum(r.get('hash_unchanged') is True for r in measured_hashes),
                               changed=sum(r.get('hash_unchanged') is False for r in measured_hashes),
                               not_measured=len(records) - len(measured_hashes)),
                jpeg=dict(mae_measured=len(maes), mean_mae=sum(maes) / len(maes) if maes else None,
                          structure_measured=sum('jpeg_structure' in r for r in records),
                          structure_ok=sum(r.get('jpeg_structure', {}).get('structure_ok', False) for r in records),
                          trailing_data=sum(r.get('jpeg_structure', {}).get('trailing_bytes', 0) > 0 for r in records)),
                alerts=alerts, pairs=pairs, rule_options=rule_options or {}, ml=deepcopy(ml),
                records=records, limitations=LIMITATIONS)


def register_fonts():
    """Nhúng TrueType có dấu tiếng Việt, không dùng font PDF mặc định."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [(Path('C:/Windows/Fonts/arial.ttf'), Path('C:/Windows/Fonts/arialbd.ttf')),
                  (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))]
    for normal, bold in candidates:
        if normal.is_file() and bold.is_file():
            if 'Vietnamese' not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont('Vietnamese', str(normal)))
                pdfmetrics.registerFont(TTFont('VietnameseBold', str(bold)))
                pdfmetrics.registerFontFamily('Vietnamese', normal='Vietnamese', bold='VietnameseBold', italic='Vietnamese', boldItalic='VietnameseBold')
            return
    raise ValueError('Không tìm được Arial hoặc DejaVu Sans để nhúng tiếng Việt Unicode.')


def bar_chart(labels, values, title, width=480, height=175):
    """Biểu đồ vector đơn giản; dữ liệu đúng số liệu đã phân tích."""
    from reportlab.graphics.shapes import Drawing, Rect, String
    register_fonts()
    drawing = Drawing(width, height)
    drawing.add(String(0, height - 15, title, fontName='VietnameseBold', fontSize=10))
    peak = max(values, default=0) or 1
    space = (width - 20) / max(1, len(values))
    for i, (label, value) in enumerate(zip(labels, values)):
        x = 10 + i * space
        h = 105 * value / peak
        drawing.add(Rect(x, 35, space * 0.65, h, fillColor=__import__('reportlab.lib.colors', fromlist=['HexColor']).HexColor('#2d6890'), strokeColor=None))
        drawing.add(String(x, 40 + h, str(value), fontName='Vietnamese', fontSize=9))
        drawing.add(String(x, 18, str(label), fontName='Vietnamese', fontSize=8))
    return drawing


def export_pdf(report, path):
    """Dùng Platypus tự ngắt trang, nhúng font và ghi ngày giờ minh bạch."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    register_fonts()
    target = protect_output(path, report['records'])
    normal = ParagraphStyle('VI', fontName='Vietnamese', fontSize=9.5, leading=14, spaceAfter=7)
    heading = ParagraphStyle('VIHeading', parent=normal, fontName='VietnameseBold', fontSize=14, leading=19, spaceBefore=12, spaceAfter=9, textColor=colors.HexColor('#154666'))
    small = ParagraphStyle('VISmall', parent=normal, fontSize=8, leading=11)
    story = []

    def paragraph(text, style=normal):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), style)

    def section(title):
        story.append(paragraph(title, heading))

    def text(value):
        story.append(paragraph(value))

    def table(rows, widths=None):
        data = [[paragraph(cell, small) for cell in row] for row in rows]
        item = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
        item.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e1edf3')),
                                  ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                  ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#bfd0da')),
                                  ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                                  ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
        story.append(item)
        story.append(Spacer(1, 8))

    section('GEO IMAGE FORENSICS ANALYZER')
    text(report['title'])
    text('Báo cáo kết quả phân tích - Giai đoạn 4')
    text('Thời gian: ' + report['analyzed_at'])
    text(report['clock_note'])
    section('1. Bộ dữ liệu và nguồn metadata')
    text(report['dataset'])
    table([['Chỉ tiêu', 'Kết quả'], ['Tổng số ảnh', report['total']],
           ['Bản ghi nguồn CSV', report['metadata']['csv']], ['Ảnh có EXIF đọc được', report['metadata']['exif_present']],
           ['GPS hợp lệ đang hiển thị', report['gps']['valid']]], [330, 150])
    text('Dữ liệu gốc CSV được giữ trong csv_original; EXIF đọc từ ảnh nằm trong exif. Các thống kê, khoảng cách, MAE, hash và nhãn ML là kết quả tính toán riêng.')
    section('2. Timeline')
    table([['Chỉ tiêu', 'Số ảnh']] + [[label, report['timeline'][key]] for label, key in
           [('Timestamp hợp lệ', 'valid'), ('Thiếu timestamp', 'missing'), ('Timestamp sai', 'invalid'),
            ('Chưa rõ múi giờ', 'unknown_timezone'), ('Bản ghi timestamp trùng', 'duplicate_records')]], [330, 150])
    story.append(PageBreak())
    section('3. Tính toàn vẹn SHA-256 và JPEG')
    integrity = report['integrity']
    table([['Kiểm tra SHA-256', 'Số ảnh'], ['Đã đo trước/sau', integrity['measured']],
           ['Hash giữ nguyên', integrity['unchanged']], ['Hash khác', integrity['changed']],
           ['Chưa có đủ hai hash', integrity['not_measured']]], [330, 150])
    jpeg = report['jpeg']
    table([['Kiểm tra JPEG', 'Kết quả'], ['Đã kiểm tra cấu trúc', jpeg['structure_measured']],
           ['Cấu trúc đạt kiểm tra cơ bản', jpeg['structure_ok']], ['Có dữ liệu sau EOI', jpeg['trailing_data']],
           ['Đã tính MAE', jpeg['mae_measured']], ['MAE trung bình', 'Chưa phân tích' if jpeg['mean_mae'] is None else f'{jpeg["mean_mae"]:.6f}']], [330, 150])
    story.append(bar_chart(['Giữ hash', 'Đổi hash', 'Chưa đo'], [integrity['unchanged'], integrity['changed'], integrity['not_measured']], 'Trạng thái đối chiếu hash'))
    section('4. Cảnh báo theo quy tắc')
    counts = Counter(a['kind'] for a in report['alerts'])
    text(f'{len(report["alerts"])} cảnh báo/thông tin; {len(report["pairs"])} cặp trong nhóm hành trình đã xác nhận.')
    text('Cấu hình luật: ' + json.dumps(report['rule_options'] or {'distance_limit': 500, 'speed_limit': 900, 'gps_difference': 0.1, 'shared_clock': False}, ensure_ascii=False))
    if counts:
        table([['Loại', 'Số lượng']] + list(counts.items()), [330, 150])
    story.append(PageBreak())
    section('5. Isolation Forest - ngoại lệ thống kê')
    ml = report['ml']
    if ml is None:
        text('Chưa chạy Machine Learning cho bộ dữ liệu này. Không tạo nhãn hoặc điểm suy đoán.')
    else:
        text('Đặc trưng: ' + ', '.join(ml['features']))
        text(f'contamination={ml["contamination"]}; random_state={ml["random_state"]}; số cây=100.')
        text('Trung vị học trên tập huấn luyện: ' + json.dumps(ml['medians'], ensure_ascii=False))
        text(ml['score_description'])
        text(ml['evaluation'])
        story.append(bar_chart(['Normal', 'Anomaly', 'Excluded'], [ml['normal'], ml['anomaly'], ml['excluded']], 'Phân bố nhãn ML'))
        scores = [r['anomaly_score'] for r in ml['results'] if r['anomaly_score'] is not None]
        if scores:
            import numpy as np
            counts, edges = np.histogram(scores, bins=8)
            story.append(bar_chart([f'{x:.2f}' for x in edges[:-1]], counts.tolist(), 'Phân bố anomaly score (mốc đầu mỗi khoảng)'))
        text('Isolation Forest chia ngẫu nhiên các đặc trưng. Điểm dễ bị cô lập qua ít lần chia thường khác biệt với phần lớn tập ảnh. contamination điều chỉnh ngưỡng gắn nhãn, không phải tỷ lệ giả mạo được chứng minh.')
    section('6. Giới hạn và diễn giải')
    text(report['limitations'])
    if ml is not None:
        story.append(PageBreak())
        section('7. Kết quả ML theo ảnh')
        table([['Ảnh', 'Nhãn', 'Anomaly score']] + [[r['file'], r['label'], '' if r['anomaly_score'] is None else f'{r["anomaly_score"]:.6f}'] for r in ml['results']], [270, 100, 110])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Vietnamese', 8)
        canvas.drawString(42, 25, 'GeoImageForensics - Kết quả thăm dò, không kết luận giả mạo')
        canvas.drawRightString(A4[0] - 42, 25, f'Trang {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=45, leftMargin=45, topMargin=36, bottomMargin=44,
                            title='Báo cáo phân tích ảnh số', author='GeoImageForensics')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return str(target)
