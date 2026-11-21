"""GPS Forensics: tính hợp lệ, DMS và đối chiếu theo độ tọa độ."""
from copy import deepcopy
import pytest
from core.gps import gps_decimal, valid_gps, normalize_gps, compare_gps_sources


def record(name='a', lon=0, stamp='2025-01-01T00:00:00Z'):
    return dict(file=name, latitude=0, longitude=lon, timestamp=stamp,
                timestamp_source='EXIF', exif={'latitude': 0, 'longitude': lon})


@pytest.mark.parametrize('lat,lon', [(0,0),(-90,-180),(90,180),('10.25','106.5')])
def test_valid_coordinates(lat, lon):
    assert valid_gps(lat, lon)


@pytest.mark.parametrize('lat,lon', [(91,0),(0,181),(float('nan'),0),(0,float('inf')),
                                     (None,0),('',0),('bad',0),(True,0),([],0),({},0)])
def test_reject_invalid_or_missing(lat, lon):
    assert not valid_gps(lat, lon)


@pytest.mark.parametrize('values,ref,expected', [((10,15,0),'N',10.25),((10,15,0),'S',-10.25),
                                                ((106,30,0),'E',106.5),((180,0,0),'W',-180),((90,0,0),b'N',90)])
def test_dms_valid(values, ref, expected):
    assert gps_decimal(values, ref) == expected


@pytest.mark.parametrize('values,ref', [(None,'N'),('123','N'),((1,2),'N'),((1,60,0),'N'),
                                       ((1,0,60),'N'),((-1,0,0),'N'),((90,0,1),'N'),((181,0,0),'E'),
                                       ((float('nan'),0,0),'N'),((1,0,float('inf')),'N'),((1,0,0),'X'),
                                       ((True,0,0),'N'),((1,0,0),None)])
def test_dms_invalid(values, ref):
    assert gps_decimal(values, ref) is None


def test_normalize_without_mutation():
    values = [' 10.25 ', '106.5']
    before = deepcopy(values)
    result = normalize_gps(*values)
    assert result['status'] == 'valid' and result['latitude'] == 10.25
    assert result['raw_latitude'] == values[0] and values == before
    assert normalize_gps(None, '')['status'] == 'missing'
    assert normalize_gps('NaN', '')['status'] == 'invalid'


@pytest.mark.parametrize('other,status', [((10,106),'match'),((10.00005,106.00005),'match'),
                                         ((10.001,106),'difference'),((10,106.001),'difference'),
                                         ((None,106),'insufficient'),((91,106),'insufficient')])
def test_compare_sources(other, status):
    result = compare_gps_sources({'lat':'10','lon':'106'}, other)
    assert result['status'] == status
    assert result['gps_tolerance_deg'] == 0.0001
    if status == 'insufficient':
        assert result['latitude_delta_deg'] is None
        assert result['longitude_delta_deg'] is None


def test_threshold_boundary_zero_and_no_coordinate_wrapping():
    assert compare_gps_sources((0,0),(0.0001,0))['status'] == 'match'
    assert compare_gps_sources((0,0),(0,0),0)['status'] == 'match'
    assert compare_gps_sources((0,0),(1e-16,0),0)['status'] == 'difference'
    assert compare_gps_sources((0,180),(0,-180))['longitude_delta_deg'] == 360


@pytest.mark.parametrize('value', [-1,float('nan'),float('inf'),None,True,'bad'])
def test_invalid_tolerance(value):
    with pytest.raises(ValueError):
        compare_gps_sources((0,0),(0,0),value)


def test_exif_dms_parse_error_retains_evidence(tmp_path):
    from PIL import Image
    from core.metadata import read_exif
    from core.anomaly import analyze_rules
    from core.integrity import sha256_file
    path = tmp_path / 'gps.jpg'
    exif = Image.Exif()
    exif[34853] = {1:'N',2:(10,0,61),3:'E',4:(106,0,0)}
    Image.new('RGB',(10,10)).save(path,exif=exif)
    before = sha256_file(path)
    metadata = read_exif(path)
    result = analyze_rules([dict(file=path.name,timestamp='',exif=metadata)])
    assert metadata['gps_parse_invalid']
    assert 'GPSLatitude' in metadata['gps_raw']
    assert any(a['kind']=='gps_invalid' and a['source']=='EXIF' for a in result['alerts'])
    assert sha256_file(path) == before
