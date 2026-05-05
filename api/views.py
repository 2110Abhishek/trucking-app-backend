from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timezone
from .services.routing import geocode, get_route, get_coord_at_distance
from .services.hos_calculator import HOSSimulator

class CalculateRouteView(APIView):
    def post(self, request):
        data = request.data
        current_loc = data.get('current_location', 'Los Angeles, CA')
        pickup_loc = data.get('pickup_location', 'Las Vegas, NV')
        dropoff_loc = data.get('dropoff_location', 'Denver, CO')
        cycle_used = float(data.get('cycle_used', 0.0))
        
        try:
            coords_current = geocode(current_loc)
            coords_pickup = geocode(pickup_loc)
            coords_dropoff = geocode(dropoff_loc)
            
            route_cp = get_route([coords_current, coords_pickup])
            route_pd = get_route([coords_pickup, coords_dropoff])
            
            leg1 = route_cp['routes'][0]
            leg2 = route_pd['routes'][0]
            
            full_geometry = leg1['geometry']['coordinates'] + leg2['geometry']['coordinates']
            
            leg1_dist = leg1['distance'] * 0.000621371
            leg1_dur = leg1['duration'] / 3600.0
            leg2_dist = leg2['distance'] * 0.000621371
            leg2_dur = leg2['duration'] / 3600.0
            
            # Start at 8 AM local time (simulated)
            start_time = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
            sim = HOSSimulator(start_time, cycle_used)
            
            # Pre-trip
            sim.add_event("on_duty", 0.25, "Pre-trip Inspection", current_loc, coords_current)
            # Leg 1
            sim.simulate_driving(leg1_dist, leg1_dur, current_loc, pickup_loc)
            # Pickup
            sim.add_event("on_duty", 1.0, f"Loading at {pickup_loc}", pickup_loc, coords_pickup)
            # Leg 2
            sim.simulate_driving(leg2_dist, leg2_dur, pickup_loc, dropoff_loc)
            # Dropoff
            sim.add_event("on_duty", 1.0, f"Unloading at {dropoff_loc}", dropoff_loc, coords_dropoff)
            # Post-trip
            sim.add_event("on_duty", 0.25, "Post-trip Inspection", dropoff_loc, coords_dropoff)
            
            # Resolve coordinates for events missing them
            fuel_stops_for_map = []
            for event in sim.timeline:
                if not event.get('coords'):
                    dist = event.get('distance_at_event', 0.0)
                    event['coords'] = get_coord_at_distance(full_geometry, dist)
                
                if "Fuel Stop" in event['description']:
                    fuel_stops_for_map.append({
                        "location": event['coords'],
                        "type": "Fuel",
                        "name": f"Fuel Stop at {round(event['distance_at_event'], 1)} mi"
                    })
                elif "Rest" in event['description'] or "Break" in event['description']:
                    fuel_stops_for_map.append({
                        "location": event['coords'],
                        "type": "Rest",
                        "name": event['description']
                    })

            return Response({
                "route_geometry": full_geometry,
                "stops": [
                    {"location": coords_current, "type": "Start", "name": current_loc},
                    {"location": coords_pickup, "type": "Pickup", "name": pickup_loc},
                    {"location": coords_dropoff, "type": "Dropoff", "name": dropoff_loc}
                ],
                "extra_markers": fuel_stops_for_map,
                "logs": sim.logs,
                "timeline": sim.timeline,
                "summary": {
                    "total_distance_miles": round(sim.total_distance, 1),
                    "total_duration_hours": round((sim.current_time - start_time).total_seconds() / 3600.0, 1),
                    "final_cycle_used": round(sim.cycle_duty, 1)
                }
            })
            
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
