"""Tạo bản đồ bằng Folium, không viết JavaScript thủ công."""
from html import escape
import folium
from core.gps import valid_gps


def create_map(records):
    """Chỉ tạo marker GPS hợp lệ; không mặc định nối thành hành trình."""
    valid = [r for r in records if valid_gps(r.get('latitude'), r.get('longitude'))]
    result = folium.Map(location=[0, 0], zoom_start=2)
    points = []
    for record in valid:
        point = [float(record['latitude']), float(record['longitude'])]
        points.append(point)
        source = 'CSV' if 'csv_original' in record else 'EXIF'
        text = escape(f'{record["file"]} | {record.get("timestamp") or "Không rõ thời gian"} | GPS {point[0]}, {point[1]} | Nguồn: {source}')
        folium.Marker(point, tooltip=text, popup=folium.Popup(text, max_width=450)).add_to(result)
    if len(points) == 1:
        result.location = points[0]
    elif points:
        result.fit_bounds(points)
    return result


def export_map(records, output):
    """Dùng cùng một bản đồ cho giao diện và xuất HTML."""
    create_map(records).save(str(output))
