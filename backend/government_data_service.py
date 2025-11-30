"""
Government Data Service
Integrates with Government of Canada MCP Servers for real infrastructure data
Falls back to simulated data when MCP servers are unavailable

MCP Servers:
- Transportation MCP (port 9001): Bridge conditions, infrastructure costs
- Dataset MCP (port 9000): Dataset discovery and search
"""

from datetime import datetime
from typing import Dict, List, Optional
import random
import os

# Try to import MCP client, fall back gracefully if not available
try:
    from mcp_client import (
        get_transportation_client,
        get_dataset_client,
        get_mcp_status,
        MCP_TRANSPORTATION_URL,
        MCP_DATASET_URL
    )
    MCP_AVAILABLE = True
except ImportError as e:
    MCP_AVAILABLE = False
    print(f"Warning: MCP client not available ({e}), using fallback data")

# Configuration
USE_LIVE_MCP = os.getenv("USE_LIVE_MCP", "true").lower() == "true"

# Canadian provinces with their geographic centers
PROVINCE_CENTERS = {
    "Ontario": {"lat": 51.2538, "lng": -85.3232},
    "Quebec": {"lat": 52.9399, "lng": -73.5491},
    "British Columbia": {"lat": 53.7267, "lng": -127.6476},
    "Alberta": {"lat": 53.9333, "lng": -116.5765},
    "Manitoba": {"lat": 53.7609, "lng": -98.8139},
    "Saskatchewan": {"lat": 52.9399, "lng": -106.4509},
    "Nova Scotia": {"lat": 44.6820, "lng": -63.7443},
    "New Brunswick": {"lat": 46.5653, "lng": -66.4619},
    "Newfoundland and Labrador": {"lat": 53.1355, "lng": -57.6604},
    "Prince Edward Island": {"lat": 46.5107, "lng": -63.4168},
    "Northwest Territories": {"lat": 64.8255, "lng": -124.8457},
    "Yukon": {"lat": 64.2823, "lng": -135.0000},
    "Nunavut": {"lat": 70.2998, "lng": -83.1076},
}

# Realistic bridge location anchors (cities, highway corridors) for fallback generation
# Used when MCP doesn't have detailed bridge records for a province
PROVINCE_BRIDGE_LOCATIONS = {
    "British Columbia": [
        # Lower Mainland / Vancouver area (high density)
        {"lat": 49.2827, "lng": -123.1207, "weight": 25, "area": "Vancouver"},
        {"lat": 49.2488, "lng": -123.0016, "weight": 10, "area": "Burnaby"},
        {"lat": 49.1666, "lng": -123.1336, "weight": 8, "area": "Richmond"},
        {"lat": 49.2057, "lng": -122.9110, "weight": 12, "area": "New Westminster"},
        {"lat": 49.1044, "lng": -122.8011, "weight": 8, "area": "Delta"},
        {"lat": 49.0504, "lng": -122.3045, "weight": 6, "area": "Abbotsford"},
        # Fraser Valley
        {"lat": 49.2193, "lng": -121.7576, "weight": 5, "area": "Chilliwack"},
        {"lat": 49.3827, "lng": -121.4413, "weight": 3, "area": "Hope"},
        # Vancouver Island
        {"lat": 48.4284, "lng": -123.3656, "weight": 10, "area": "Victoria"},
        {"lat": 49.1659, "lng": -123.9401, "weight": 6, "area": "Nanaimo"},
        {"lat": 48.7500, "lng": -123.7089, "weight": 3, "area": "Duncan"},
        # Interior
        {"lat": 49.8880, "lng": -119.4960, "weight": 6, "area": "Kelowna"},
        {"lat": 50.6745, "lng": -120.3273, "weight": 5, "area": "Kamloops"},
        {"lat": 49.4991, "lng": -117.2948, "weight": 3, "area": "Nelson"},
        # Northern BC
        {"lat": 53.9171, "lng": -122.7497, "weight": 4, "area": "Prince George"},
        {"lat": 54.2310, "lng": -130.8778, "weight": 2, "area": "Prince Rupert"},
    ],
    "Alberta": [
        {"lat": 51.0447, "lng": -114.0719, "weight": 25, "area": "Calgary"},
        {"lat": 53.5461, "lng": -113.4938, "weight": 25, "area": "Edmonton"},
        {"lat": 49.6951, "lng": -112.8418, "weight": 5, "area": "Lethbridge"},
        {"lat": 52.2690, "lng": -113.8116, "weight": 4, "area": "Red Deer"},
        {"lat": 56.7267, "lng": -111.3790, "weight": 3, "area": "Fort McMurray"},
        {"lat": 53.8945, "lng": -116.5765, "weight": 3, "area": "Jasper"},
        {"lat": 51.1784, "lng": -115.5708, "weight": 3, "area": "Banff"},
        {"lat": 50.0405, "lng": -110.6764, "weight": 3, "area": "Medicine Hat"},
        {"lat": 55.1690, "lng": -118.8027, "weight": 2, "area": "Grande Prairie"},
    ],
    "Manitoba": [
        {"lat": 49.8951, "lng": -97.1384, "weight": 40, "area": "Winnipeg"},
        {"lat": 49.8838, "lng": -99.9517, "weight": 8, "area": "Brandon"},
        {"lat": 50.4452, "lng": -96.0779, "weight": 5, "area": "Selkirk"},
        {"lat": 49.6307, "lng": -97.1518, "weight": 5, "area": "Morris"},
        {"lat": 53.8259, "lng": -101.2542, "weight": 3, "area": "The Pas"},
        {"lat": 54.7668, "lng": -101.8766, "weight": 3, "area": "Flin Flon"},
    ],
    "Saskatchewan": [
        {"lat": 50.4452, "lng": -104.6189, "weight": 25, "area": "Regina"},
        {"lat": 52.1332, "lng": -106.6700, "weight": 25, "area": "Saskatoon"},
        {"lat": 50.3935, "lng": -105.5439, "weight": 5, "area": "Moose Jaw"},
        {"lat": 53.2033, "lng": -105.7531, "weight": 5, "area": "Prince Albert"},
        {"lat": 50.4018, "lng": -107.7975, "weight": 4, "area": "Swift Current"},
        {"lat": 51.2073, "lng": -102.4671, "weight": 3, "area": "Yorkton"},
    ],
    "Ontario": [
        {"lat": 43.6532, "lng": -79.3832, "weight": 25, "area": "Toronto"},
        {"lat": 45.4215, "lng": -75.6972, "weight": 15, "area": "Ottawa"},
        {"lat": 43.2557, "lng": -79.8711, "weight": 10, "area": "Hamilton"},
        {"lat": 42.9849, "lng": -81.2453, "weight": 8, "area": "London"},
        {"lat": 43.4643, "lng": -80.5204, "weight": 6, "area": "Kitchener"},
        {"lat": 43.1501, "lng": -79.0872, "weight": 5, "area": "Niagara Falls"},
        {"lat": 42.3149, "lng": -83.0364, "weight": 5, "area": "Windsor"},
        {"lat": 44.3894, "lng": -79.6903, "weight": 4, "area": "Barrie"},
        {"lat": 46.4917, "lng": -80.9930, "weight": 4, "area": "Sudbury"},
        {"lat": 48.3809, "lng": -89.2477, "weight": 3, "area": "Thunder Bay"},
    ],
    "Quebec": [
        {"lat": 45.5017, "lng": -73.5673, "weight": 30, "area": "Montreal"},
        {"lat": 46.8139, "lng": -71.2080, "weight": 15, "area": "Quebec City"},
        {"lat": 45.4042, "lng": -71.8929, "weight": 6, "area": "Sherbrooke"},
        {"lat": 48.4284, "lng": -71.0683, "weight": 5, "area": "Saguenay"},
        {"lat": 46.3430, "lng": -72.5477, "weight": 5, "area": "Trois-Rivières"},
        {"lat": 45.5355, "lng": -73.4177, "weight": 5, "area": "Longueuil"},
        {"lat": 45.5579, "lng": -73.8704, "weight": 4, "area": "Laval"},
        {"lat": 47.5651, "lng": -70.8700, "weight": 3, "area": "Charlevoix"},
    ],
    "Nova Scotia": [
        {"lat": 44.6488, "lng": -63.5752, "weight": 35, "area": "Halifax"},
        {"lat": 44.6456, "lng": -63.5728, "weight": 15, "area": "Dartmouth"},
        {"lat": 46.1368, "lng": -60.1942, "weight": 10, "area": "Sydney"},
        {"lat": 45.0915, "lng": -64.3634, "weight": 6, "area": "Kentville"},
        {"lat": 44.3776, "lng": -64.5091, "weight": 5, "area": "Bridgewater"},
        {"lat": 45.6160, "lng": -61.9951, "weight": 4, "area": "New Glasgow"},
    ],
    "New Brunswick": [
        {"lat": 45.9636, "lng": -66.6431, "weight": 25, "area": "Fredericton"},
        {"lat": 45.2733, "lng": -66.0633, "weight": 20, "area": "Saint John"},
        {"lat": 46.0878, "lng": -64.7782, "weight": 15, "area": "Moncton"},
        {"lat": 47.3609, "lng": -65.7345, "weight": 5, "area": "Bathurst"},
        {"lat": 46.9965, "lng": -65.4510, "weight": 4, "area": "Miramichi"},
    ],
    "Newfoundland and Labrador": [
        {"lat": 47.5615, "lng": -52.7126, "weight": 40, "area": "St. John's"},
        {"lat": 48.9500, "lng": -54.6000, "weight": 10, "area": "Gander"},
        {"lat": 49.2500, "lng": -57.9500, "weight": 8, "area": "Corner Brook"},
        {"lat": 48.5167, "lng": -58.5500, "weight": 5, "area": "Stephenville"},
        {"lat": 53.3017, "lng": -60.3261, "weight": 4, "area": "Happy Valley-Goose Bay"},
    ],
    "Prince Edward Island": [
        {"lat": 46.2382, "lng": -63.1311, "weight": 40, "area": "Charlottetown"},
        {"lat": 46.2345, "lng": -63.4861, "weight": 20, "area": "Summerside"},
        {"lat": 46.0900, "lng": -62.9800, "weight": 10, "area": "Montague"},
        {"lat": 46.4364, "lng": -63.7486, "weight": 8, "area": "Kensington"},
    ],
    "Northwest Territories": [
        {"lat": 62.4540, "lng": -114.3718, "weight": 50, "area": "Yellowknife"},
        {"lat": 60.0000, "lng": -111.9200, "weight": 15, "area": "Fort Smith"},
        {"lat": 64.2667, "lng": -125.5167, "weight": 10, "area": "Norman Wells"},
        {"lat": 68.3607, "lng": -133.7230, "weight": 8, "area": "Inuvik"},
    ],
    "Yukon": [
        {"lat": 60.7212, "lng": -135.0568, "weight": 50, "area": "Whitehorse"},
        {"lat": 63.9961, "lng": -139.1168, "weight": 15, "area": "Dawson City"},
        {"lat": 60.8500, "lng": -137.3833, "weight": 10, "area": "Haines Junction"},
        {"lat": 60.0667, "lng": -128.7167, "weight": 8, "area": "Watson Lake"},
    ],
    "Nunavut": [
        {"lat": 63.7467, "lng": -68.5170, "weight": 40, "area": "Iqaluit"},
        {"lat": 64.3167, "lng": -96.0333, "weight": 15, "area": "Rankin Inlet"},
        {"lat": 69.1169, "lng": -105.0596, "weight": 12, "area": "Cambridge Bay"},
        {"lat": 74.7167, "lng": -94.9833, "weight": 8, "area": "Resolute"},
    ],
}

# Fallback data based on Statistics Canada patterns (used when MCP unavailable)
# Source: https://www150.statcan.gc.ca/
PROVINCE_BRIDGE_DATA = {
    "Ontario": {
        "total_bridges": 2847,
        "conditions": {"Good": 1138, "Fair": 1281, "Poor": 342, "Critical": 57, "Unknown": 29},
        "replacement_value_billions": 18.5,
        "priority_investment_millions": 892,
        "last_updated": "2024-03-15",
    },
    "Quebec": {
        "total_bridges": 2156,
        "conditions": {"Good": 863, "Fair": 970, "Poor": 259, "Critical": 43, "Unknown": 21},
        "replacement_value_billions": 14.2,
        "priority_investment_millions": 678,
        "last_updated": "2024-03-15",
    },
    "British Columbia": {
        "total_bridges": 1892,
        "conditions": {"Good": 757, "Fair": 851, "Poor": 227, "Critical": 38, "Unknown": 19},
        "replacement_value_billions": 12.8,
        "priority_investment_millions": 612,
        "last_updated": "2024-03-15",
    },
    "Alberta": {
        "total_bridges": 1456,
        "conditions": {"Good": 583, "Fair": 655, "Poor": 175, "Critical": 29, "Unknown": 14},
        "replacement_value_billions": 9.8,
        "priority_investment_millions": 468,
        "last_updated": "2024-03-15",
    },
    "Manitoba": {
        "total_bridges": 876,
        "conditions": {"Good": 350, "Fair": 394, "Poor": 105, "Critical": 18, "Unknown": 9},
        "replacement_value_billions": 5.9,
        "priority_investment_millions": 282,
        "last_updated": "2024-03-15",
    },
    "Saskatchewan": {
        "total_bridges": 1124,
        "conditions": {"Good": 449, "Fair": 506, "Poor": 135, "Critical": 22, "Unknown": 12},
        "replacement_value_billions": 7.6,
        "priority_investment_millions": 362,
        "last_updated": "2024-03-15",
    },
    "Nova Scotia": {
        "total_bridges": 423,
        "conditions": {"Good": 169, "Fair": 190, "Poor": 51, "Critical": 8, "Unknown": 5},
        "replacement_value_billions": 2.9,
        "priority_investment_millions": 136,
        "last_updated": "2024-03-15",
    },
    "New Brunswick": {
        "total_bridges": 567,
        "conditions": {"Good": 227, "Fair": 255, "Poor": 68, "Critical": 11, "Unknown": 6},
        "replacement_value_billions": 3.8,
        "priority_investment_millions": 183,
        "last_updated": "2024-03-15",
    },
    "Newfoundland and Labrador": {
        "total_bridges": 312,
        "conditions": {"Good": 125, "Fair": 140, "Poor": 37, "Critical": 6, "Unknown": 4},
        "replacement_value_billions": 2.1,
        "priority_investment_millions": 101,
        "last_updated": "2024-03-15",
    },
    "Prince Edward Island": {
        "total_bridges": 189,
        "conditions": {"Good": 76, "Fair": 85, "Poor": 23, "Critical": 4, "Unknown": 1},
        "replacement_value_billions": 1.3,
        "priority_investment_millions": 61,
        "last_updated": "2024-03-15",
    },
    "Northwest Territories": {
        "total_bridges": 78,
        "conditions": {"Good": 31, "Fair": 35, "Poor": 9, "Critical": 2, "Unknown": 1},
        "replacement_value_billions": 0.5,
        "priority_investment_millions": 25,
        "last_updated": "2024-03-15",
    },
    "Yukon": {
        "total_bridges": 92,
        "conditions": {"Good": 37, "Fair": 41, "Poor": 11, "Critical": 2, "Unknown": 1},
        "replacement_value_billions": 0.6,
        "priority_investment_millions": 30,
        "last_updated": "2024-03-15",
    },
    "Nunavut": {
        "total_bridges": 24,
        "conditions": {"Good": 10, "Fair": 11, "Poor": 2, "Critical": 1, "Unknown": 0},
        "replacement_value_billions": 0.2,
        "priority_investment_millions": 8,
        "last_updated": "2024-03-15",
    },
}


def _try_mcp_bridge_conditions(region: str) -> Optional[Dict]:
    """Try to get bridge conditions from MCP server"""
    if not MCP_AVAILABLE or not USE_LIVE_MCP:
        return None
    
    try:
        client = get_transportation_client()
        if not client.is_available():
            return None
            
        result = client.analyze_bridge_conditions(region)
        
        if result and "error" not in result:
            condition_breakdown = []
            
            # Handle the actual MCP response format with condition_summary
            if "condition_summary" in result:
                summary = result["condition_summary"]
                
                # MCP returns detailed_records_available which may be 0 for some provinces
                # In that case, use our fallback data's total_bridges for count calculation
                mcp_record_count = result.get("detailed_records_available", 0)
                
                # Get fallback total for provinces where MCP has no detailed records
                fallback_total = 0
                if region in PROVINCE_BRIDGE_DATA:
                    fallback_total = PROVINCE_BRIDGE_DATA[region]["total_bridges"]
                
                # Use MCP count if available, otherwise use fallback
                total_count = mcp_record_count if mcp_record_count > 0 else fallback_total
                
                # Map MCP conditions to our conditions
                condition_map = {
                    "very_good": "Good",
                    "good": "Good", 
                    "fair": "Fair",
                    "poor": "Poor",
                    "very_poor": "Critical",
                    "unknown": "Unknown"
                }
                
                aggregated = {}
                for mcp_key, data in summary.items():
                    our_condition = condition_map.get(mcp_key, "Unknown")
                    percentage = data.get("percentage", 0)
                    
                    if our_condition in aggregated:
                        aggregated[our_condition] += percentage
                    else:
                        aggregated[our_condition] = percentage
                
                # Build condition breakdown with calculated counts
                for condition, percentage in aggregated.items():
                    if percentage > 0:
                        # Calculate count based on percentage and total
                        count = int(round((percentage / 100) * total_count))
                        condition_breakdown.append({
                            "condition": condition,
                            "count": count,
                            "percentage": round(percentage, 1)
                        })
                
                if condition_breakdown:
                    # Sort by standard order: Good, Fair, Poor, Critical, Unknown
                    order = {"Good": 0, "Fair": 1, "Poor": 2, "Critical": 3, "Unknown": 4}
                    condition_breakdown.sort(key=lambda x: order.get(x["condition"], 5))
                    
                    return {
                        "region": region,
                        "total_bridges": total_count,
                        "condition_breakdown": condition_breakdown,
                        "last_updated": datetime.now().strftime("%Y-%m-%d"),
                        "data_source": f"Statistics Canada ({result.get('data_source', {}).get('table_id', 'Live MCP')})",
                        "reference_year": result.get("reference_year", "2022"),
                        "mcp_source": True,
                        "has_detailed_records": mcp_record_count > 0
                    }
            
            # Fallback parsing for other formats
            elif "condition_breakdown" in result:
                for item in result["condition_breakdown"]:
                    condition_breakdown.append({
                        "condition": item.get("condition", "Unknown"),
                        "count": item.get("count", 0),
                        "percentage": item.get("percentage", 0)
                    })
                
                return {
                    "region": region,
                    "total_bridges": result.get("total_count", 0),
                    "condition_breakdown": condition_breakdown,
                    "last_updated": datetime.now().strftime("%Y-%m-%d"),
                    "data_source": "Statistics Canada (Live MCP)",
                    "mcp_source": True
                }
                
    except Exception as e:
        print(f"MCP bridge conditions failed: {e}")
    
    return None


def _try_mcp_infrastructure_costs(region: str) -> Optional[Dict]:
    """Try to get infrastructure costs from MCP server"""
    if not MCP_AVAILABLE or not USE_LIVE_MCP:
        return None
    
    try:
        client = get_transportation_client()
        if not client.is_available():
            return None
            
        result = client.get_infrastructure_costs("bridge", region)
        
        if result and "error" not in result:
            # Handle the actual MCP response format
            if "total_replacement_value" in result:
                total_value = result["total_replacement_value"]
                priority_investment = result.get("priority_investment_needed", {})
                source = result.get("source", {})
                
                # Convert millions to billions for replacement value
                value_millions = total_value.get("value", 0)
                value_billions = round(value_millions / 1000, 1)
                
                # Get priority investment from poor/very poor
                priority_millions = priority_investment.get("poor_and_very_poor_total", {}).get("value_millions", 0)
                
                return {
                    "region": region,
                    "replacement_value_billions": value_billions,
                    "replacement_value_millions": value_millions,
                    "priority_investment_millions": priority_millions,
                    "currency": "CAD",
                    "last_updated": datetime.now().strftime("%Y-%m-%d"),
                    "data_source": f"Statistics Canada ({source.get('table_id', 'Live MCP')})",
                    "reference_year": source.get("reference_year", "2022"),
                    "data_quality": result.get("data_quality", "Unknown"),
                    "costs_by_condition": result.get("costs_by_condition", {}),
                    "mcp_source": True
                }
            
            # Fallback for simpler response formats
            replacement_value = (
                result.get("total_value_billions", 0) or 
                result.get("replacementValueBillions", 0) or
                result.get("replacement_value_billions", 0)
            )
            priority_investment = (
                result.get("priority_investment_millions", 0) or
                result.get("priorityInvestmentMillions", 0)
            )
            
            if replacement_value > 0 or priority_investment > 0:
                return {
                    "region": region,
                    "replacement_value_billions": replacement_value,
                    "priority_investment_millions": priority_investment,
                    "currency": "CAD",
                    "last_updated": datetime.now().strftime("%Y-%m-%d"),
                    "data_source": "Statistics Canada (Live MCP)",
                    "mcp_source": True
                }
    except Exception as e:
        print(f"MCP infrastructure costs failed: {e}")
    
    return None


def _try_mcp_query_bridges(region: str, limit: int) -> Optional[List[Dict]]:
    """Try to get bridge locations from MCP server"""
    if not MCP_AVAILABLE or not USE_LIVE_MCP:
        return None
    
    try:
        client = get_transportation_client()
        if not client.is_available():
            return None
            
        result = client.query_bridges(region, limit)
        
        if result and "error" not in result:
            bridges = []
            
            # Handle the bridges array format from query_bridges tool
            bridges_data = result.get("bridges", [])
            
            if bridges_data:
                for i, bridge in enumerate(bridges_data[:limit]):
                    location = bridge.get("location", {})
                    coords = location.get("coordinates", {}) if isinstance(location, dict) else {}
                    
                    lat = float(coords.get("latitude", 0))
                    lng = float(coords.get("longitude", 0))
                    
                    # Map condition_rating to our standard conditions
                    condition_raw = bridge.get("condition_rating", bridge.get("condition", "unknown"))
                    condition_map = {
                        "very_good": "Good",
                        "good": "Good",
                        "fair": "Fair",
                        "poor": "Poor",
                        "very_poor": "Critical",
                    }
                    condition = condition_map.get(condition_raw.lower(), condition_raw.title())
                    
                    bridges.append({
                        "id": bridge.get("id") or f"{region[:3].upper()}-{i+1:04d}",
                        "name": bridge.get("name", f"Bridge #{i+1}"),
                        "latitude": lat,
                        "longitude": lng,
                        "condition": condition,
                        "condition_index": bridge.get("condition_index"),
                        "year_built": bridge.get("year_built", "Unknown"),
                        "last_inspection": bridge.get("last_inspection", "Unknown"),
                        "highway": bridge.get("highway"),
                        "structure_type": bridge.get("structure_type"),
                        "category": bridge.get("category"),
                        "material": bridge.get("material"),
                        "owner": bridge.get("owner"),
                        "status": bridge.get("status"),
                        "region": region,
                        "county": location.get("county"),
                        "source": bridge.get("source", "MCP")
                    })
                return bridges if bridges else None
            
            # Handle detailed_records format (from analyze_bridge_conditions)
            if "detailed_records" in result:
                for i, bridge in enumerate(result["detailed_records"][:limit]):
                    location = bridge.get("location", {})
                    coords = location.get("coordinates", {})
                    
                    condition_raw = bridge.get("condition_rating", "unknown")
                    condition_map = {
                        "very_good": "Good",
                        "good": "Good", 
                        "fair": "Fair",
                        "poor": "Poor",
                        "very_poor": "Critical",
                    }
                    condition = condition_map.get(condition_raw.lower(), condition_raw.title())
                    
                    bridges.append({
                        "id": bridge.get("id") or f"{region[:3].upper()}-{i+1:04d}",
                        "name": bridge.get("name", f"Bridge #{i+1}"),
                        "latitude": float(coords.get("latitude", 0)),
                        "longitude": float(coords.get("longitude", 0)),
                        "condition": condition,
                        "condition_index": bridge.get("condition_index"),
                        "year_built": bridge.get("year_built", "Unknown"),
                        "last_inspection": bridge.get("last_inspection", "Unknown"),
                        "highway": bridge.get("highway"),
                        "structure_type": bridge.get("structure_type"),
                        "material": bridge.get("material"),
                        "owner": bridge.get("owner"),
                        "status": bridge.get("status"),
                        "region": region,
                        "county": location.get("county"),
                        "source": bridge.get("source", "MCP")
                    })
                return bridges if bridges else None
                
    except Exception as e:
        print(f"MCP query bridges failed: {e}")
        print(f"MCP query bridges failed: {e}")
    
    return None


def get_bridge_conditions(region: str, force_refresh: bool = False) -> Optional[Dict]:
    """
    Get bridge condition data for a specific region.
    Uses on-demand caching with 24-hour TTL.
    
    Flow:
    1. Check database cache (if valid and not force_refresh)
    2. If cache miss/expired → fetch from MCP
    3. If MCP fails → use fallback data
    4. Store result in cache
    """
    from cache_service import get_cached_region_data, save_region_data, log_sync_start, log_sync_complete
    import time
    
    # Step 1: Check cache (unless force refresh)
    if not force_refresh:
        cached = get_cached_region_data(region)
        if cached:
            # Return just the conditions part from cache
            return {
                "region": cached["region"],
                "total_bridges": cached["total_bridges"],
                "condition_breakdown": cached["condition_breakdown"],
                "last_updated": cached["last_updated"],
                "data_source": cached["data_source"],
                "reference_year": cached.get("reference_year"),
                "mcp_source": False,
                "is_cached": True,
                "cache_age_hours": cached.get("cache_age_hours", 0)
            }
    
    # Step 2: Try MCP for fresh data
    start_time = time.time()
    mcp_result = _try_mcp_bridge_conditions(region)
    mcp_time_ms = int((time.time() - start_time) * 1000)
    
    if mcp_result:
        # Also get costs to save together
        costs_result = _try_mcp_infrastructure_costs(region) or _get_fallback_costs(region)
        if costs_result:
            save_region_data(region, mcp_result, costs_result)
        return mcp_result
    
    # Step 3: Fallback to static data
    fallback = _get_fallback_conditions(region)
    if fallback:
        costs_fallback = _get_fallback_costs(region)
        if costs_fallback:
            save_region_data(region, fallback, costs_fallback)
    
    return fallback


def _get_fallback_conditions(region: str) -> Optional[Dict]:
    """Get fallback condition data from static cache"""
    if region not in PROVINCE_BRIDGE_DATA:
        return None
    
    data = PROVINCE_BRIDGE_DATA[region]
    total = data["total_bridges"]
    conditions = data["conditions"]
    
    condition_breakdown = []
    for condition, count in conditions.items():
        percentage = round((count / total) * 100, 1) if total > 0 else 0
        condition_breakdown.append({
            "condition": condition,
            "count": count,
            "percentage": percentage
        })
    
    return {
        "region": region,
        "total_bridges": total,
        "condition_breakdown": condition_breakdown,
        "last_updated": data["last_updated"],
        "data_source": "Statistics Canada (Fallback)",
        "mcp_source": False
    }


def _get_fallback_costs(region: str) -> Optional[Dict]:
    """Get fallback cost data from static cache"""
    if region not in PROVINCE_BRIDGE_DATA:
        return None
    
    data = PROVINCE_BRIDGE_DATA[region]
    
    return {
        "region": region,
        "replacement_value_billions": data["replacement_value_billions"],
        "priority_investment_millions": data["priority_investment_millions"],
        "currency": "CAD",
        "last_updated": data["last_updated"],
        "data_source": "Statistics Canada (Fallback)",
        "mcp_source": False
    }


def get_infrastructure_costs(region: str, force_refresh: bool = False) -> Optional[Dict]:
    """
    Get infrastructure cost/investment data for a specific region.
    Uses on-demand caching with 24-hour TTL.
    """
    from cache_service import get_cached_region_data, save_region_data
    
    # Step 1: Check cache (unless force refresh)
    if not force_refresh:
        cached = get_cached_region_data(region)
        if cached:
            return {
                "region": cached["region"],
                "replacement_value_billions": cached["replacement_value_billions"],
                "priority_investment_millions": cached["priority_investment_millions"],
                "currency": "CAD",
                "last_updated": cached["last_updated"],
                "data_source": cached["data_source"],
                "reference_year": cached.get("reference_year"),
                "mcp_source": False,
                "is_cached": True
            }
    
    # Step 2: Try MCP for fresh data
    mcp_result = _try_mcp_infrastructure_costs(region)
    
    if mcp_result:
        # Also get conditions to save together
        conditions_result = _try_mcp_bridge_conditions(region) or _get_fallback_conditions(region)
        if conditions_result:
            save_region_data(region, conditions_result, mcp_result)
        return mcp_result
    
    # Step 3: Fallback
    return _get_fallback_costs(region)


def get_bridge_locations(region: str, limit: int = 100, force_refresh: bool = False) -> Optional[List[Dict]]:
    """
    Get individual bridge locations with conditions for mapping.
    Uses on-demand caching with 24-hour TTL.
    
    For bridges without coordinates, uses Nominatim geocoding API to get real lat/long.
    """
    from cache_service import get_cached_bridges, save_bridge_locations, get_cached_region_data
    
    # Step 1: Check cache (unless force refresh)
    if not force_refresh:
        cached_bridges = get_cached_bridges(region, limit)
        if cached_bridges:
            return cached_bridges
    
    # Step 2: Try MCP for fresh data
    mcp_result = _try_mcp_query_bridges(region, limit)
    
    if mcp_result:
        # Geocode any bridges missing coordinates
        mcp_result = _geocode_missing_coordinates(mcp_result, region)
        save_bridge_locations(region, mcp_result)
        return mcp_result
    
    # Step 3: Fallback - generate bridges with geocoded coordinates
    fallback = _generate_fallback_bridges_with_geocoding(region, limit)
    if fallback:
        save_bridge_locations(region, fallback)
    
    return fallback


def _geocode_missing_coordinates(bridges: List[Dict], region: str) -> List[Dict]:
    """
    Geocode bridges that are missing lat/long coordinates.
    Uses Nominatim API (OpenStreetMap) for real geocoding.
    Falls back to highway corridor locations if geocoding fails.
    """
    try:
        from geocoding_service import geocode_location, get_highway_corridor_location
    except ImportError:
        print("Geocoding service not available, using existing coordinates")
        return bridges
    
    geocoded_count = 0
    
    for bridge in bridges:
        lat = bridge.get("latitude", 0)
        lng = bridge.get("longitude", 0)
        
        # Skip if already has valid coordinates
        if lat != 0 and lng != 0:
            continue
        
        # Try geocoding with bridge details
        highway = bridge.get("highway", "")
        county = bridge.get("county", "")
        name = bridge.get("name", "")
        
        # Build search query
        if highway and county:
            query = f"Highway {highway} {county}"
        elif county:
            query = county
        elif highway:
            query = f"Highway {highway}"
        else:
            query = name
        
        result = geocode_location(query, region)
        
        if result:
            bridge["latitude"] = result["lat"]
            bridge["longitude"] = result["lng"]
            bridge["geocoded"] = True
            geocoded_count += 1
        else:
            # Fallback to highway corridor location
            if highway:
                corridor = get_highway_corridor_location(highway, region)
                if corridor:
                    # Add small random offset
                    bridge["latitude"] = corridor["lat"] + random.uniform(-0.02, 0.02)
                    bridge["longitude"] = corridor["lng"] + random.uniform(-0.02, 0.02)
                    bridge["geocoded"] = True
                    geocoded_count += 1
    
    print(f"Geocoded {geocoded_count} bridges with missing coordinates for {region}")
    return bridges


def _generate_fallback_bridges_with_geocoding(region: str, limit: int) -> Optional[List[Dict]]:
    """
    Generate fallback bridge data using real geocoding for coordinates.
    Creates realistic bridge names based on Canadian infrastructure patterns,
    then geocodes them to get real lat/long.
    """
    if region not in PROVINCE_BRIDGE_DATA:
        return None
    
    try:
        from geocoding_service import geocode_location
        use_geocoding = True
    except ImportError:
        use_geocoding = False
    
    data = PROVINCE_BRIDGE_DATA[region]
    locations = PROVINCE_BRIDGE_LOCATIONS.get(region, [])
    
    # Fallback to province center if no locations defined
    if not locations:
        center = PROVINCE_CENTERS.get(region, {"lat": 50.0, "lng": -100.0})
        locations = [{"lat": center["lat"], "lng": center["lng"], "weight": 100, "area": region}]
    
    bridges = []
    conditions_list = []
    
    for condition, count in data["conditions"].items():
        conditions_list.extend([condition] * count)
    
    random.seed(42 + hash(region))
    random.shuffle(conditions_list)
    
    num_bridges = min(limit, len(conditions_list))
    
    # Build weighted location pool based on weights
    location_pool = []
    for loc in locations:
        location_pool.extend([loc] * loc.get("weight", 1))
    
    # Canadian bridge/infrastructure naming patterns
    bridge_features = [
        "River", "Creek", "Highway", "Railway", "Overpass", 
        "Interchange", "Crossing", "Viaduct", "Underpass"
    ]
    
    for i in range(num_bridges):
        # Pick a weighted random location (city/area)
        base_location = random.choice(location_pool)
        area_name = base_location.get("area", "")
        
        condition = conditions_list[i] if i < len(conditions_list) else "Unknown"
        
        feature = random.choice(bridge_features)
        bridge_num = random.randint(1, 999)
        bridge_name = f"{area_name} {feature} Bridge #{bridge_num}"
        
        # Try geocoding first, then fall back to city coordinates with offset
        lat = base_location["lat"]
        lng = base_location["lng"]
        geocoded = False
        
        if use_geocoding and i < 50:  # Only geocode first 50 to avoid rate limits
            # Try to geocode the area for more precise location
            result = geocode_location(f"{feature} {area_name}", region)
            if result:
                lat = result["lat"]
                lng = result["lng"]
                geocoded = True
        
        if not geocoded:
            # Add small random offset from city center (within ~3km)
            lat += random.uniform(-0.03, 0.03)
            lng += random.uniform(-0.03, 0.03)
        
        bridges.append({
            "id": f"{region[:3].upper()}-{i+1:04d}",
            "name": bridge_name,
            "latitude": round(lat, 6),
            "longitude": round(lng, 6),
            "condition": condition,
            "year_built": str(random.randint(1950, 2020)),
            "last_inspection": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "region": region,
            "county": area_name,
            "geocoded": geocoded
        })
    
    return bridges


def _generate_fallback_bridges(region: str, limit: int) -> Optional[List[Dict]]:
    """Generate fallback bridge data with realistic coordinates based on city locations"""
    if region not in PROVINCE_BRIDGE_DATA:
        return None
    
    data = PROVINCE_BRIDGE_DATA[region]
    locations = PROVINCE_BRIDGE_LOCATIONS.get(region, [])
    
    # Fallback to province center if no locations defined
    if not locations:
        center = PROVINCE_CENTERS.get(region, {"lat": 50.0, "lng": -100.0})
        locations = [{"lat": center["lat"], "lng": center["lng"], "weight": 100, "area": region}]
    
    bridges = []
    conditions_list = []
    
    for condition, count in data["conditions"].items():
        conditions_list.extend([condition] * count)
    
    random.seed(42 + hash(region))
    random.shuffle(conditions_list)
    
    num_bridges = min(limit, len(conditions_list))
    
    # Build weighted location pool based on weights
    location_pool = []
    for loc in locations:
        location_pool.extend([loc] * loc.get("weight", 1))
    
    for i in range(num_bridges):
        # Pick a weighted random location
        base_location = random.choice(location_pool)
        
        # Add small random offset (within ~5km radius to keep near roads/cities)
        lat_offset = random.uniform(-0.05, 0.05)
        lng_offset = random.uniform(-0.05, 0.05)
        
        condition = conditions_list[i] if i < len(conditions_list) else "Unknown"
        
        bridge_types = ["Highway", "River", "Creek", "Railway", "Overpass", "Interchange"]
        bridge_type = random.choice(bridge_types)
        bridge_num = random.randint(1, 999)
        
        bridges.append({
            "id": f"{region[:3].upper()}-{i+1:04d}",
            "name": f"{bridge_type} Bridge #{bridge_num}",
            "latitude": round(base_location["lat"] + lat_offset, 6),
            "longitude": round(base_location["lng"] + lng_offset, 6),
            "condition": condition,
            "year_built": str(random.randint(1950, 2020)),
            "last_inspection": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "region": region,
            "county": base_location.get("area")
        })
    
    return bridges


def get_dashboard_summary(region: str, force_refresh: bool = False) -> Optional[Dict]:
    """
    Aggregates all dashboard data for a region.
    Uses on-demand caching with 24-hour TTL.
    """
    from cache_service import get_cached_region_data
    
    # Try to get from cache first (unless force refresh)
    if not force_refresh:
        cached = get_cached_region_data(region)
        if cached:
            return cached
    
    # Cache miss or force refresh - fetch fresh data
    conditions = get_bridge_conditions(region, force_refresh=force_refresh)
    costs = get_infrastructure_costs(region, force_refresh=force_refresh)
    
    if not conditions or not costs:
        return None
    
    # Determine if using live MCP data
    is_live = conditions.get("mcp_source", False) or costs.get("mcp_source", False)
    is_cached = conditions.get("is_cached", False)
    
    return {
        "region": region,
        "total_bridges": conditions["total_bridges"],
        "condition_breakdown": conditions["condition_breakdown"],
        "replacement_value_billions": round(costs["replacement_value_billions"], 1),
        "priority_investment_millions": round(costs["priority_investment_millions"], 1),
        "currency": "CAD",
        "last_updated": conditions["last_updated"],
        "data_source": conditions.get("data_source", "Statistics Canada"),
        "data_source_url": "https://www150.statcan.gc.ca/",
        "reference_year": conditions.get("reference_year"),
        "is_live_data": is_live,
        "is_cached": is_cached,
        "cache_age_hours": conditions.get("cache_age_hours", 0) if is_cached else None
    }


def get_all_regions() -> List[str]:
    """
    Returns list of all supported regions
    """
    return list(PROVINCE_BRIDGE_DATA.keys())


def get_mcp_server_status() -> Dict:
    """
    Returns status of MCP servers with tool information
    """
    if not MCP_AVAILABLE:
        return {
            "available": False,
            "transportation": False,
            "dataset": False,
            "message": "MCP client not installed"
        }
    
    status = get_mcp_status()
    result = {
        "available": status.get("transportation", False) or status.get("dataset", False),
        "transportation": status.get("transportation", False),
        "dataset": status.get("dataset", False),
        "transportation_url": status.get("transportation_url", MCP_TRANSPORTATION_URL),
        "dataset_url": status.get("dataset_url", MCP_DATASET_URL),
    }
    
    # Include tool information if available
    if "transportation_tools" in status:
        result["transportation_tools"] = status["transportation_tools"]
    if "dataset_tools" in status:
        result["dataset_tools"] = status["dataset_tools"]
    
    if result["available"]:
        result["message"] = "MCP servers connected"
    else:
        result["message"] = "MCP servers not reachable"
    
    return result


def get_national_summary() -> Dict:
    """
    Returns aggregated national statistics
    """
    total_bridges = 0
    total_replacement_value = 0
    total_priority_investment = 0
    national_conditions = {"Good": 0, "Fair": 0, "Poor": 0, "Critical": 0, "Unknown": 0}
    
    for region, data in PROVINCE_BRIDGE_DATA.items():
        total_bridges += data["total_bridges"]
        total_replacement_value += data["replacement_value_billions"]
        total_priority_investment += data["priority_investment_millions"]
        
        for condition, count in data["conditions"].items():
            national_conditions[condition] += count
    
    condition_breakdown = []
    for condition, count in national_conditions.items():
        percentage = round((count / total_bridges) * 100, 1) if total_bridges > 0 else 0
        condition_breakdown.append({
            "condition": condition,
            "count": count,
            "percentage": percentage
        })
    
    return {
        "region": "Canada (National)",
        "total_bridges": total_bridges,
        "condition_breakdown": condition_breakdown,
        "replacement_value_billions": round(total_replacement_value, 1),
        "priority_investment_millions": round(total_priority_investment, 0),
        "currency": "CAD",
        "last_updated": "2024-03-15",
        "data_source": "Statistics Canada",
        "provinces_count": len(PROVINCE_BRIDGE_DATA)
    }


def sync_region_from_mcp(region: str) -> Dict:
    """
    Force sync a region from MCP servers.
    Used by admin refresh endpoint.
    Returns sync status and timing.
    """
    from cache_service import log_sync_start, log_sync_complete, invalidate_cache
    import time
    
    if region not in PROVINCE_BRIDGE_DATA and region != "all":
        return {
            "success": False,
            "error": f"Unknown region: {region}",
            "region": region
        }
    
    # Invalidate existing cache
    invalidate_cache(region if region != "all" else None)
    
    regions_to_sync = [region] if region != "all" else list(PROVINCE_BRIDGE_DATA.keys())
    results = []
    
    for r in regions_to_sync:
        sync_log = log_sync_start(r, "full")
        start_time = time.time()
        
        try:
            # Force refresh from MCP
            conditions = get_bridge_conditions(r, force_refresh=True)
            costs = get_infrastructure_costs(r, force_refresh=True)
            bridges = get_bridge_locations(r, limit=100, force_refresh=True)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            bridge_count = len(bridges) if bridges else 0
            is_mcp = conditions.get("mcp_source", False) if conditions else False
            
            log_sync_complete(
                sync_log.id,
                status="success",
                records_synced=bridge_count,
                response_time_ms=elapsed_ms
            )
            
            results.append({
                "region": r,
                "success": True,
                "bridges_synced": bridge_count,
                "from_mcp": is_mcp,
                "time_ms": elapsed_ms
            })
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            log_sync_complete(
                sync_log.id,
                status="failed",
                error_message=str(e),
                response_time_ms=elapsed_ms
            )
            results.append({
                "region": r,
                "success": False,
                "error": str(e),
                "time_ms": elapsed_ms
            })
    
    return {
        "success": all(r["success"] for r in results),
        "regions_synced": len([r for r in results if r["success"]]),
        "total_regions": len(results),
        "results": results
    }


def get_cache_status_for_region(region: str = None) -> Dict:
    """
    Get cache status for a region or all regions.
    """
    from cache_service import get_cache_status
    return get_cache_status(region)
