import requests
import polyline
import time

# Nominatim requires a User-Agent. Using a unique one for your app.
HEADERS = {
    'User-Agent': 'TruckOS-Compliance-App/1.0 (abhishek@example.com)'
}

def geocode(location_name):
    """Converts a city/address to coordinates with retry logic for 429 errors."""
    url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
    
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS)
            if response.status_code == 429:
                time.sleep(1.5) # Wait and retry on rate limit
                continue
            
            data = response.json()
            if data:
                return [float(data[0]['lon']), float(data[0]['lat'])]
            raise Exception(f"Location '{location_name}' not found.")
        except Exception as e:
            if attempt == 2: raise e
            time.sleep(1)
    
    return None

def get_route(coords):
    """Fetches route from OSRM."""
    coord_str = ";".join([f"{c[0]},{c[1]}" for c in coords])
    url = f"http://router.project-osrm.org/route/v1/driving/{coord_str}?overview=full&geometries=polyline"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        # Decode polyline for frontend Leaflet use
        for route in data['routes']:
            route['geometry'] = {
                "type": "LineString",
                "coordinates": polyline.decode(route['geometry'])
            }
            # Swap lat/lng for Leaflet [lat, lng]
            route['geometry']['coordinates'] = [[p[0], p[1]] for p in route['geometry']['coordinates']]
        return data
    raise Exception("Failed to fetch route from OSRM.")

def get_coord_at_distance(geometry_coords, target_miles):
    """Interpolates a coordinate at a specific distance along a polyline."""
    if not geometry_coords: return None
    
    # Very simple interpolation for demo purposes
    # For a high-fidelity ELD, we map distance to the specific polyline index
    total_points = len(geometry_coords)
    progress = min(1.0, target_miles / (target_miles + 100)) # Placeholder logic
    idx = int(progress * (total_points - 1))
    return geometry_coords[idx]
