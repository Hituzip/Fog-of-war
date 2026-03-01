import gpxpy
from shapely.geometry import LineString
from geoalchemy2.shape import from_shape

def parse_gpx_to_linestring(gpx_file) -> LineString:
    gpx = gpxpy.parse(gpx_file)
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append((point.longitude, point.latitude))
    if len(points) < 2:
        raise ValueError("GPX must contain at least 2 points")
    return LineString(points)