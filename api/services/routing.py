import requests
import time

def geocode(location_string):
    """
    Convert a location string (e.g. 'Los Angeles, CA') to (lat, lon) coordinates
    using Nominatim API.
    """
    url = f"https://nominatim.openstreetmap.org/search"
    params = {
        'q': location_string,
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'TruckingApp/1.0'
    }
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    if data:
        return float(data[0]['lat']), float(data[0]['lon'])
    raise ValueError(f"Could not geocode location: {location_string}")

def get_route(waypoints):
    """
    Fetch routing data from OSRM between a list of waypoints.
    waypoints: list of (lat, lon) tuples.
    Returns the full JSON response containing routes, duration, distance, and geometry.
    """
    # OSRM expects coordinates in lon,lat format
    coord_string = ";".join([f"{lon},{lat}" for lat, lon in waypoints])
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_string}"
    params = {
        'overview': 'full',
        'geometries': 'geojson',
        'steps': 'true'
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def calculate_distance(p1, p2):
    """Haversine distance between two points (lat, lon)."""
    import math
    R = 3958.8 # Earth radius in miles
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_coord_at_distance(polyline_coords, target_miles):
    """
    Finds the (lat, lon) coordinate at target_miles along the polyline.
    polyline_coords: list of [lon, lat] (standard GeoJSON format from OSRM)
    """
    accumulated_miles = 0.0
    for i in range(len(polyline_coords) - 1):
        p1 = [polyline_coords[i][1], polyline_coords[i][0]] # [lat, lon]
        p2 = [polyline_coords[i+1][1], polyline_coords[i+1][0]]
        dist = calculate_distance(p1, p2)
        if accumulated_miles + dist >= target_miles:
            # Linear interpolation
            remaining = target_miles - accumulated_miles
            ratio = remaining / dist if dist > 0 else 0
            lat = p1[0] + (p2[0] - p1[0]) * ratio
            lon = p1[1] + (p2[1] - p1[1]) * ratio
            return lat, lon
        accumulated_miles += dist
    return polyline_coords[-1][1], polyline_coords[-1][0]
