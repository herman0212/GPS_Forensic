"""Marker GPS tách theo nguồn, Folium tự sinh HTML/JavaScript."""
from html import escape
import folium
from core.gps import gps_sources


def create_map(records):
    """Mỗi nguồn hợp lệ có marker riêng; không suy diễn quan hệ giữa các ảnh."""
    result = folium.Map(location=[0, 0], zoom_start=2)
    points = []
    colors = {'CSV': 'blue', 'EXIF': 'green', 'reference': 'gray'}
    layers = {name: folium.FeatureGroup(name='GPS ' + name).add_to(result) for name in colors}
    for record in records:
        for source, gps in gps_sources(record).items():
            if gps['status'] != 'valid':
                continue
            point = [gps['latitude'], gps['longitude']]
            points.append(point)
            label = 'Tham chiếu / chưa xác định nguồn' if source == 'reference' else source
            text = escape(f'{record.get("file", "")} | {record.get("timestamp") or "Không rõ thời gian"} | GPS {point[0]}, {point[1]} | Nguồn: {label}')
            folium.Marker(point, tooltip=text, popup=folium.Popup(text, max_width=450),
                          icon=folium.Icon(color=colors[source])).add_to(layers[source])
    folium.LayerControl(collapsed=False).add_to(result)
    if len(points) == 1:
        result.location = points[0]
    elif points:
        result.fit_bounds(points)
    return result


def export_map(records, output):
    """Lưu cùng bản đồ được dùng trong giao diện."""
    create_map(records).save(str(output))
