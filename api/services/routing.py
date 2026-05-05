import requests
import polyline
import time

# Demo Cache for common cities - Standardized to [lat, lon] for Leaflet
GEO_CACHE = {
    "los angeles, ca": [34.0549, -118.2426],
    "las vegas, nv": [36.1699, -115.1398],
    "new york, ny": [40.7128, -74.0060],
    "denver, co": [39.7392, -104.9903],
    "chicago, il": [41.8781, -87.6298],
    "miami, fl": [25.7617, -80.1918],
    "la": [34.0549, -118.2426],
    "lv": [36.1699, -115.1398],
    "ny": [40.7128, -74.0060]
}

HEADERS = {
    'User-Agent': 'TruckOS-HOS-Compliance/1.0 (abhishek-demo@render.com)'
}

def geocode(location_name):
    """Converts a city/address to coordinates with a local cache fallback."""
    clean_name = location_name.lower().strip()
    
    if clean_name in GEO_CACHE:
        return GEO_CACHE[clean_name]
    
    url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 429:
                time.sleep(2)
                continue
            
            data = response.json()
            if data:
                # Return [lat, lon] for consistency
                return [float(data[0]['lat']), float(data[0]['lon'])]
            raise Exception(f"Location '{location_name}' not found.")
        except Exception as e:
            if attempt == 2: raise e
            time.sleep(1)
    
    return None

def get_route(coords):
    """Fetches route from OSRM. Expects [[lat, lon], ...]"""
    # OSRM expects lon,lat;lon,lat
    coord_str = ";".join([f"{c[1]},{c[0]}" for c in coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=polyline"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        for route in data['routes']:
            # polyline.decode returns [[lat, lon], ...]
            route['geometry'] = {
                "type": "LineString",
                "coordinates": polyline.decode(route['geometry'])
            }
        return data
    raise Exception("Failed to fetch route from OSRM.")

def get_coord_at_distance(geometry_coords, target_miles):
    """Interpolates a coordinate at a specific distance along a polyline."""
    if not geometry_coords: return None
    total_points = len(geometry_coords)
    progress = min(0.99, target_miles / 3000.0) 
    idx = int(progress * (total_points - 1))
    return geometry_coords[idx]
