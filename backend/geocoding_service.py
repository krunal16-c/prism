"""
Geocoding Service
Uses OpenStreetMap Nominatim API to get real lat/long coordinates for bridge locations.
Free, no API key required, good coverage of Canadian infrastructure.

Rate limit: 1 request per second (we batch and cache results)
"""

import httpx
import asyncio
import time
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

# Nominatim API (OpenStreetMap - free, no API key)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# User agent required by Nominatim ToS
USER_AGENT = "PRISM-Infrastructure-Dashboard/1.0 (https://github.com/prism)"

# Rate limiting: 1 request per second
RATE_LIMIT_DELAY = 1.1

# Last request timestamp for rate limiting
_last_request_time = 0


async def geocode_location_async(query: str, province: str = None) -> Optional[Dict]:
    """
    Geocode a location query to get lat/long coordinates.
    
    Args:
        query: Location name (e.g., "Highway 401 Toronto", "Fraser River Bridge Vancouver")
        province: Province to narrow search (e.g., "British Columbia")
    
    Returns:
        Dict with lat, lng, display_name or None if not found
    """
    global _last_request_time
    
    # Rate limiting
    elapsed = time.time() - _last_request_time
    if elapsed < RATE_LIMIT_DELAY:
        await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
    
    # Build search query with province context
    search_query = query
    if province:
        search_query = f"{query}, {province}, Canada"
    else:
        search_query = f"{query}, Canada"
    
    params = {
        "q": search_query,
        "format": "json",
        "limit": 1,
        "countrycodes": "ca",
    }
    
    headers = {
        "User-Agent": USER_AGENT,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            _last_request_time = time.time()
            response = await client.get(NOMINATIM_URL, params=params, headers=headers)
            
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    result = results[0]
                    return {
                        "lat": float(result["lat"]),
                        "lng": float(result["lon"]),
                        "display_name": result.get("display_name", ""),
                        "type": result.get("type", ""),
                        "importance": result.get("importance", 0),
                    }
    except Exception as e:
        print(f"Geocoding failed for '{query}': {e}")
    
    return None


def geocode_location(query: str, province: str = None) -> Optional[Dict]:
    """Sync wrapper for geocode_location_async"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, geocode_location_async(query, province))
                return future.result(timeout=15.0)
        else:
            return loop.run_until_complete(geocode_location_async(query, province))
    except RuntimeError:
        return asyncio.run(geocode_location_async(query, province))


async def geocode_bridge_location_async(
    bridge_name: str,
    highway: str = None,
    area: str = None,
    province: str = None
) -> Optional[Dict]:
    """
    Geocode a bridge with multiple fallback strategies.
    
    Tries in order:
    1. Bridge name + highway + province
    2. Highway + area + province  
    3. Area + province (city/town)
    4. Highway corridor in province
    """
    queries = []
    
    # Strategy 1: Full bridge query
    if bridge_name and highway:
        queries.append(f"{bridge_name} {highway}")
    
    # Strategy 2: Highway + area
    if highway and area:
        queries.append(f"Highway {highway} {area}")
    
    # Strategy 3: Just the area (city/town)
    if area:
        queries.append(area)
    
    # Strategy 4: Highway in province
    if highway:
        queries.append(f"Highway {highway}")
    
    # Try each query until we get a result
    for query in queries:
        result = await geocode_location_async(query, province)
        if result:
            return result
    
    return None


async def geocode_bridges_batch_async(
    bridges: List[Dict],
    province: str
) -> List[Dict]:
    """
    Geocode a batch of bridges with rate limiting.
    Updates bridges in place with lat/lng coordinates.
    
    Args:
        bridges: List of bridge dicts with 'name', 'highway', 'county' fields
        province: Province name for context
    
    Returns:
        Updated bridges list with geocoded coordinates
    """
    geocoded_count = 0
    failed_count = 0
    
    for bridge in bridges:
        # Skip if already has valid coordinates
        if bridge.get("latitude") and bridge.get("longitude"):
            if bridge["latitude"] != 0 and bridge["longitude"] != 0:
                continue
        
        # Try to geocode
        result = await geocode_bridge_location_async(
            bridge_name=bridge.get("name"),
            highway=bridge.get("highway"),
            area=bridge.get("county") or bridge.get("area"),
            province=province
        )
        
        if result:
            bridge["latitude"] = result["lat"]
            bridge["longitude"] = result["lng"]
            bridge["geocoded"] = True
            geocoded_count += 1
        else:
            failed_count += 1
            bridge["geocoded"] = False
    
    print(f"Geocoded {geocoded_count} bridges, {failed_count} failed for {province}")
    return bridges


def geocode_bridges_batch(bridges: List[Dict], province: str) -> List[Dict]:
    """Sync wrapper for geocode_bridges_batch_async"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, geocode_bridges_batch_async(bridges, province))
                return future.result(timeout=300.0)  # 5 min timeout for batch
        else:
            return loop.run_until_complete(geocode_bridges_batch_async(bridges, province))
    except RuntimeError:
        return asyncio.run(geocode_bridges_batch_async(bridges, province))


# Pre-defined highway corridors for faster geocoding fallback
# These are approximate corridor centerpoints when specific geocoding fails
HIGHWAY_CORRIDORS = {
    "British Columbia": {
        "1": {"lat": 49.2827, "lng": -123.1207, "name": "Trans-Canada Highway"},
        "99": {"lat": 49.1913, "lng": -123.1780, "name": "Sea to Sky Highway"},
        "97": {"lat": 53.9171, "lng": -122.7497, "name": "Cariboo Highway"},
        "5": {"lat": 50.6745, "lng": -120.3273, "name": "Coquihalla Highway"},
        "3": {"lat": 49.3267, "lng": -117.6614, "name": "Crowsnest Highway"},
    },
    "Ontario": {
        "401": {"lat": 43.6532, "lng": -79.3832, "name": "Highway 401"},
        "400": {"lat": 44.3894, "lng": -79.6903, "name": "Highway 400"},
        "403": {"lat": 43.2557, "lng": -79.8711, "name": "Highway 403"},
        "404": {"lat": 43.8078, "lng": -79.3868, "name": "Highway 404"},
        "407": {"lat": 43.7615, "lng": -79.4111, "name": "Highway 407"},
        "417": {"lat": 45.4215, "lng": -75.6972, "name": "Highway 417"},
        "QEW": {"lat": 43.1501, "lng": -79.0872, "name": "Queen Elizabeth Way"},
    },
    "Quebec": {
        "20": {"lat": 45.5017, "lng": -73.5673, "name": "Autoroute 20"},
        "40": {"lat": 45.5579, "lng": -73.8704, "name": "Autoroute 40"},
        "15": {"lat": 45.5017, "lng": -73.5673, "name": "Autoroute 15"},
        "10": {"lat": 45.4042, "lng": -71.8929, "name": "Autoroute 10"},
    },
    "Alberta": {
        "2": {"lat": 51.0447, "lng": -114.0719, "name": "Queen Elizabeth II Highway"},
        "1": {"lat": 51.0447, "lng": -114.0719, "name": "Trans-Canada Highway"},
        "63": {"lat": 56.7267, "lng": -111.3790, "name": "Highway 63"},
    },
}


def get_highway_corridor_location(highway: str, province: str) -> Optional[Dict]:
    """Get approximate location for a highway corridor as fallback"""
    province_highways = HIGHWAY_CORRIDORS.get(province, {})
    
    # Try exact match
    if highway in province_highways:
        return province_highways[highway]
    
    # Try without leading zeros or letters
    highway_clean = highway.lstrip("0").upper()
    for key, value in province_highways.items():
        if key.lstrip("0").upper() == highway_clean:
            return value
    
    return None
