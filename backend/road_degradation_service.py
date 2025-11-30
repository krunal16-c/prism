"""
Road Degradation Forecasting Service
Feature 10: Highway Degradation Forecaster

Predicts road condition deterioration using:
- PCI (Pavement Condition Index) degradation curves
- Traffic volume impacts
- Climate zone factors
- Pavement type degradation rates
- Maintenance history effects

Uses `query_road_condition` MCP tool for real data.
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum

from mcp_client import get_transportation_client


class ClimateZone(Enum):
    """Canadian climate zones affecting pavement degradation"""
    ARCTIC = "arctic"           # Northern territories - extreme freeze-thaw
    COLD = "cold"               # Prairies, Northern Ontario - severe winters
    MODERATE = "moderate"       # Southern Ontario, Quebec - 4 seasons
    MILD = "mild"               # BC Coast, Southern NS - mild winters
    MOUNTAIN = "mountain"       # Rocky Mountains - altitude effects


class PavementType(Enum):
    """Pavement types with different degradation characteristics"""
    AC = "AC"           # Asphalt Concrete - most common
    PCC = "PCC"         # Portland Cement Concrete - longer life
    COMPOSITE = "COMP"  # Composite - AC over PCC
    SURFACE_TREATED = "ST"  # Surface treated
    GRAVEL = "GRAVEL"   # Unpaved


@dataclass
class DegradationForecast:
    """Forecast for a single road segment"""
    highway: str
    section: str
    current_pci: float
    predicted_pci: Dict[int, float]  # year -> PCI
    years_to_critical: int
    optimal_intervention_year: int
    optimal_intervention_pci: float
    estimated_cost_now: float
    estimated_cost_optimal: float
    estimated_cost_delayed: float
    cost_savings_optimal: float
    degradation_rate: float  # PCI points per year


@dataclass
class EconomicImpact:
    """Economic impact of road condition"""
    highway: str
    section: str
    pci: float
    condition: str
    daily_traffic: int
    annual_vehicle_damage_cost: float
    annual_fuel_waste_cost: float
    annual_freight_delay_cost: float
    total_annual_cost: float
    roi_if_repaired: float


# Climate zone mapping for Canadian provinces
PROVINCE_CLIMATE_ZONES: Dict[str, ClimateZone] = {
    "British Columbia": ClimateZone.MILD,  # Coast areas
    "Alberta": ClimateZone.COLD,
    "Saskatchewan": ClimateZone.COLD,
    "Manitoba": ClimateZone.COLD,
    "Ontario": ClimateZone.MODERATE,
    "Quebec": ClimateZone.MODERATE,
    "New Brunswick": ClimateZone.MODERATE,
    "Nova Scotia": ClimateZone.MODERATE,
    "Prince Edward Island": ClimateZone.MODERATE,
    "Newfoundland and Labrador": ClimateZone.COLD,
    "Yukon": ClimateZone.ARCTIC,
    "Northwest Territories": ClimateZone.ARCTIC,
    "Nunavut": ClimateZone.ARCTIC,
}

# Climate zone degradation multipliers (base is 1.0)
CLIMATE_DEGRADATION_FACTORS: Dict[ClimateZone, float] = {
    ClimateZone.ARCTIC: 1.5,      # Extreme freeze-thaw, permafrost
    ClimateZone.COLD: 1.3,        # Severe winters, salt usage
    ClimateZone.MODERATE: 1.0,    # Baseline
    ClimateZone.MILD: 0.8,        # Mild conditions
    ClimateZone.MOUNTAIN: 1.4,    # Altitude, steep grades
}

# Pavement type base degradation rates (PCI points/year at moderate climate)
PAVEMENT_BASE_DEGRADATION: Dict[str, float] = {
    "AC": -4.5,      # Asphalt - moderate degradation
    "PCC": -2.5,     # Concrete - slower degradation
    "COMP": -3.5,    # Composite - between AC and PCC
    "ST": -6.0,      # Surface treated - faster degradation
    "GRAVEL": -8.0,  # Gravel - fastest
    "UNKNOWN": -5.0, # Default
}

# Traffic volume impact factors (AADT-based)
TRAFFIC_DEGRADATION_FACTORS = [
    (5000, 0.8),      # < 5000 AADT: 0.8x
    (15000, 1.0),     # 5000-15000: 1.0x (baseline)
    (30000, 1.3),     # 15000-30000: 1.3x
    (50000, 1.6),     # 30000-50000: 1.6x
    (100000, 2.0),    # 50000-100000: 2.0x
    (float('inf'), 2.5),  # > 100000: 2.5x
]

# Intervention cost per square meter by condition
INTERVENTION_COSTS = {
    "preventive": 8.0,      # PCI >= 70: Seal coating, crack sealing
    "corrective": 25.0,     # PCI 50-69: Mill and overlay
    "rehabilitation": 45.0, # PCI 30-49: Full depth reclamation
    "reconstruction": 65.0, # PCI < 30: Complete rebuild
}

# PCI thresholds
PCI_THRESHOLDS = {
    "good": 80,
    "fair": 60,
    "poor": 40,
    "critical": 0,
}


def get_traffic_factor(aadt: int) -> float:
    """Get degradation multiplier based on average annual daily traffic"""
    if aadt is None:
        aadt = 15000  # Default to moderate traffic
    for threshold, factor in TRAFFIC_DEGRADATION_FACTORS:
        if aadt < threshold:
            return factor
    return 2.5


def get_pci_acceleration_factor(pci: float) -> float:
    """
    PCI degradation accelerates below 60.
    - Above 70: Normal rate (1.0x)
    - 60-70: Slight acceleration (1.2x)
    - 50-60: Moderate acceleration (1.5x)
    - 40-50: Significant acceleration (1.8x)
    - Below 40: Rapid acceleration (2.2x)
    """
    if pci >= 70:
        return 1.0
    elif pci >= 60:
        return 1.2
    elif pci >= 50:
        return 1.5
    elif pci >= 40:
        return 1.8
    else:
        return 2.2


def calculate_degradation_rate(
    current_pci: float,
    pavement_type: str,
    climate_zone: ClimateZone,
    aadt: int = 15000,
    pavement_age: int = None,
    maintenance_score: float = 1.0
) -> float:
    """
    Calculate annual PCI degradation rate.
    
    Returns negative value (PCI points lost per year).
    Typical range: -3 to -8 PCI points/year.
    """
    # Base rate from pavement type
    base_rate = PAVEMENT_BASE_DEGRADATION.get(pavement_type, -5.0)
    
    # Climate factor
    climate_factor = CLIMATE_DEGRADATION_FACTORS.get(climate_zone, 1.0)
    
    # Traffic factor
    traffic_factor = get_traffic_factor(aadt)
    
    # PCI acceleration (degradation speeds up as condition worsens)
    pci_factor = get_pci_acceleration_factor(current_pci)
    
    # Age factor (older pavements degrade faster)
    age_factor = 1.0
    if pavement_age is not None:
        if pavement_age > 20:
            age_factor = 1.3
        elif pavement_age > 15:
            age_factor = 1.15
        elif pavement_age > 10:
            age_factor = 1.0
        else:
            age_factor = 0.9
    
    # Maintenance factor (well-maintained = slower degradation)
    # maintenance_score: 0.8 (excellent) to 1.3 (poor)
    
    # Calculate final rate
    final_rate = base_rate * climate_factor * traffic_factor * pci_factor * age_factor * maintenance_score
    
    # Clamp to reasonable range (-2 to -12 PCI/year)
    return max(-12.0, min(-2.0, final_rate))


def forecast_pci(
    current_pci: float,
    years: int,
    pavement_type: str,
    climate_zone: ClimateZone,
    aadt: int = 15000,
    pavement_age: int = None
) -> Dict[int, float]:
    """
    Forecast PCI values for each year.
    Returns dict of {year: predicted_pci}.
    """
    predictions = {0: current_pci}
    pci = current_pci
    
    for year in range(1, years + 1):
        # Recalculate rate each year as PCI changes
        rate = calculate_degradation_rate(
            pci, pavement_type, climate_zone, aadt, 
            pavement_age + year if pavement_age else None
        )
        pci = max(0, pci + rate)
        predictions[year] = round(pci, 1)
    
    return predictions


def find_optimal_intervention(
    forecast: Dict[int, float],
    current_pci: float
) -> Tuple[int, float, float, float, float]:
    """
    Find optimal intervention window.
    Returns: (year, pci_at_intervention, cost_now, cost_optimal, cost_delayed)
    
    Intervention costs ($/m²):
    - PCI >= 70: $8 (preventive)
    - PCI 50-69: $25 (corrective)
    - PCI 30-49: $45 (rehabilitation)
    - PCI < 30: $65 (reconstruction)
    """
    # Assume standard lane width (3.7m) and 1km section = 3,700 m²
    area_per_km = 3700  # m²
    
    def get_cost_per_m2(pci: float) -> float:
        if pci >= 70:
            return INTERVENTION_COSTS["preventive"]
        elif pci >= 50:
            return INTERVENTION_COSTS["corrective"]
        elif pci >= 30:
            return INTERVENTION_COSTS["rehabilitation"]
        else:
            return INTERVENTION_COSTS["reconstruction"]
    
    cost_now = get_cost_per_m2(current_pci) * area_per_km
    
    # Find optimal year (lowest total lifecycle cost)
    # Optimal is typically when PCI is around 65-70 (corrective but not too late)
    optimal_year = 0
    optimal_pci = current_pci
    min_lifecycle_cost = float('inf')
    
    for year, pci in forecast.items():
        if pci <= 25:  # Don't wait until reconstruction needed
            break
        
        cost = get_cost_per_m2(pci) * area_per_km
        # Add time-value discount (3% per year)
        discounted_cost = cost / ((1.03) ** year)
        
        # If we can do preventive maintenance, that's often optimal
        if pci >= 65 and pci <= 75 and discounted_cost < min_lifecycle_cost:
            min_lifecycle_cost = discounted_cost
            optimal_year = year
            optimal_pci = pci
    
    # If no optimal found, use year when PCI hits 65
    if optimal_year == 0:
        for year, pci in forecast.items():
            if pci <= 70:
                optimal_year = year
                optimal_pci = pci
                break
    
    cost_optimal = get_cost_per_m2(optimal_pci) * area_per_km
    
    # Delayed cost (if wait until PCI hits 30)
    delayed_pci = 30
    for year, pci in forecast.items():
        if pci <= 30:
            delayed_pci = pci
            break
    cost_delayed = get_cost_per_m2(delayed_pci) * area_per_km
    
    return (optimal_year, optimal_pci, cost_now, cost_optimal, cost_delayed)


def calculate_economic_impact(
    pci: float,
    aadt: int,
    section_length_km: float = 1.0,
    highway_class: str = "arterial"
) -> Dict[str, float]:
    """
    Calculate economic impact of current road condition.
    
    Returns annual costs in CAD.
    """
    # Vehicle damage costs (poor roads cause more wear)
    # Good road: $0.01/km, Poor road: $0.08/km per vehicle
    base_damage_per_km = 0.01
    if pci < 40:
        damage_factor = 8.0
    elif pci < 60:
        damage_factor = 4.0
    elif pci < 80:
        damage_factor = 2.0
    else:
        damage_factor = 1.0
    
    annual_vehicles = aadt * 365
    vehicle_damage = annual_vehicles * section_length_km * base_damage_per_km * damage_factor
    
    # Fuel waste (rough roads increase consumption by 2-10%)
    # Assume average trip uses 0.1L/km
    base_fuel_per_km = 0.1
    fuel_price = 1.60  # CAD/L
    if pci < 40:
        fuel_increase = 0.10  # 10% increase
    elif pci < 60:
        fuel_increase = 0.05  # 5% increase
    elif pci < 80:
        fuel_increase = 0.02  # 2% increase
    else:
        fuel_increase = 0.0
    
    fuel_waste = annual_vehicles * section_length_km * base_fuel_per_km * fuel_increase * fuel_price
    
    # Freight delay costs (poor roads = slower speeds)
    # Assume 20% of traffic is freight, average value of time $80/hour
    freight_share = 0.20
    freight_value_per_hour = 80.0
    
    if pci < 40:
        delay_minutes_per_km = 2.0  # 2 min delay per km
    elif pci < 60:
        delay_minutes_per_km = 0.5
    elif pci < 80:
        delay_minutes_per_km = 0.1
    else:
        delay_minutes_per_km = 0.0
    
    freight_vehicles = annual_vehicles * freight_share
    freight_delay = freight_vehicles * section_length_km * (delay_minutes_per_km / 60) * freight_value_per_hour
    
    total = vehicle_damage + fuel_waste + freight_delay
    
    # ROI if repaired (annual savings / repair cost)
    repair_cost = get_repair_cost(pci, section_length_km * 3700)  # 3700 m² per km
    roi = (total * 10 / repair_cost) if repair_cost > 0 else 0  # 10-year savings
    
    return {
        "vehicle_damage_cost": round(vehicle_damage, 2),
        "fuel_waste_cost": round(fuel_waste, 2),
        "freight_delay_cost": round(freight_delay, 2),
        "total_annual_cost": round(total, 2),
        "roi_if_repaired": round(roi, 2),
    }


def get_repair_cost(pci: float, area_m2: float) -> float:
    """Get estimated repair cost based on current PCI"""
    if pci >= 70:
        return area_m2 * INTERVENTION_COSTS["preventive"]
    elif pci >= 50:
        return area_m2 * INTERVENTION_COSTS["corrective"]
    elif pci >= 30:
        return area_m2 * INTERVENTION_COSTS["rehabilitation"]
    else:
        return area_m2 * INTERVENTION_COSTS["reconstruction"]


def get_condition_label(pci: float) -> str:
    """Get condition label from PCI"""
    if pci >= 80:
        return "good"
    elif pci >= 60:
        return "fair"
    elif pci >= 40:
        return "poor"
    else:
        return "critical"


class RoadDegradationService:
    """Service for road condition forecasting and analysis"""
    
    def __init__(self):
        self.mcp_client = get_transportation_client()
        self._cache_ttl = timedelta(hours=24)
    
    def _get_db_session(self):
        """Get a database session"""
        from database import SessionLocal
        return SessionLocal()
    
    def _get_cached_roads_from_db(
        self, 
        province: str = None, 
        highway: str = None,
        condition: str = None,
        limit: int = 100
    ) -> Optional[List[Dict]]:
        """Get cached road data from database if available and fresh"""
        from models import CachedRoadCondition
        from sqlalchemy import and_
        
        db = self._get_db_session()
        try:
            # Build query
            query = db.query(CachedRoadCondition)
            
            if province:
                query = query.filter(CachedRoadCondition.province == province)
            if highway:
                query = query.filter(CachedRoadCondition.highway.ilike(f"%{highway}%"))
            if condition:
                query = query.filter(CachedRoadCondition.condition.ilike(condition))
            
            # Check if cache is fresh (any record within TTL)
            cutoff = datetime.now(timezone.utc) - self._cache_ttl
            fresh_check = query.filter(CachedRoadCondition.cached_at >= cutoff).first()
            
            if not fresh_check:
                return None  # Cache is stale or empty
            
            # Get all matching records
            records = query.limit(limit).all()
            
            if not records:
                return None
            
            # Convert to dict format
            roads = []
            for r in records:
                roads.append({
                    "highway": r.highway,
                    "direction": r.direction,
                    "section_from": r.section_from,
                    "section_to": r.section_to,
                    "km_start": r.km_start,
                    "km_end": r.km_end,
                    "pci": r.pci,
                    "condition": r.condition,
                    "dmi": r.dmi,
                    "iri": r.iri,
                    "pavement_type": r.pavement_type,
                    "functional_class": r.functional_class,
                    "aadt": r.aadt,
                    "pavement_age": r.pavement_age,
                    "province": r.province,
                    "lat": r.lat,
                    "lng": r.lng,
                })
            
            return roads
        finally:
            db.close()
    
    def _cache_roads_to_db(self, roads: List[Dict], source: str = "MCP"):
        """Cache road data to database"""
        from models import CachedRoadCondition
        
        if not roads:
            return
        
        db = self._get_db_session()
        try:
            # Get province from first road for bulk delete
            province = roads[0].get("province") if roads else None
            highway = roads[0].get("highway") if roads else None
            
            # Delete old cached data for this province/highway combination
            if province and highway:
                db.query(CachedRoadCondition).filter(
                    CachedRoadCondition.province == province,
                    CachedRoadCondition.highway == highway
                ).delete()
            elif province:
                db.query(CachedRoadCondition).filter(
                    CachedRoadCondition.province == province
                ).delete()
            
            # Insert new records
            now = datetime.now(timezone.utc)
            for road in roads:
                # Handle MCP field name differences (from_km vs km_start, latitude vs lat)
                km_start = road.get("km_start") or road.get("from_km")
                km_end = road.get("km_end") or road.get("to_km")
                lat = road.get("lat") or road.get("latitude")
                lng = road.get("lng") or road.get("longitude")
                
                cached = CachedRoadCondition(
                    province=road.get("province", ""),
                    highway=road.get("highway", ""),
                    direction=road.get("direction"),
                    section_from=road.get("section_from"),
                    section_to=road.get("section_to"),
                    km_start=km_start,
                    km_end=km_end,
                    pci=road.get("pci"),
                    condition=road.get("condition"),
                    dmi=road.get("dmi"),
                    iri=road.get("iri"),
                    pavement_type=road.get("pavement_type"),
                    functional_class=road.get("functional_class"),
                    aadt=road.get("aadt"),
                    pavement_age=road.get("pavement_age"),
                    lat=lat,
                    lng=lng,
                    cached_at=now,
                    data_source=source
                )
                db.add(cached)
            
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to cache roads to DB: {e}")
        finally:
            db.close()
    
    def get_road_conditions(
        self,
        province: str = None,
        highway: str = None,
        condition: str = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get road conditions from database cache, MCP, or generate fallback data.
        Priority: 1) Fresh DB cache, 2) MCP (then cache), 3) Generated fallback (then cache)
        """
        # 1. Try database cache first
        cached_roads = self._get_cached_roads_from_db(province, highway, condition, limit)
        if cached_roads:
            return {"roads": cached_roads, "source": "database_cache"}
        
        # 2. Try MCP and cache results
        if self.mcp_client.is_available():
            try:
                result = self.mcp_client.query_road_condition(
                    province=province,
                    highway=highway,
                    condition=condition,
                    limit=limit
                )
                if result and result.get("roads"):
                    # Normalize field names and add province
                    roads = result["roads"]
                    normalized_roads = []
                    for road in roads:
                        if not road.get("province") and province:
                            road["province"] = province
                        # Normalize MCP field names to standard names
                        normalized = {
                            "highway": road.get("highway"),
                            "direction": road.get("direction"),
                            "section_from": road.get("section_from"),
                            "section_to": road.get("section_to"),
                            "km_start": road.get("km_start") or road.get("from_km"),
                            "km_end": road.get("km_end") or road.get("to_km"),
                            "pci": road.get("pci"),
                            "condition": road.get("condition"),
                            "dmi": road.get("dmi"),
                            "iri": road.get("iri"),
                            "pavement_type": road.get("pavement_type"),
                            "functional_class": road.get("functional_class"),
                            "aadt": road.get("aadt"),
                            "pavement_age": road.get("pavement_age"),
                            "province": road.get("province"),
                            "lat": road.get("lat") or road.get("latitude"),
                            "lng": road.get("lng") or road.get("longitude"),
                        }
                        normalized_roads.append(normalized)
                    # Cache to database
                    self._cache_roads_to_db(normalized_roads, source="MCP")
                    return {"roads": normalized_roads, "source": "MCP"}
            except Exception as e:
                print(f"MCP road query failed: {e}")
        
        # 3. Generate fallback data and cache it
        roads = self._generate_fallback_roads(province, highway, condition, limit)
        if roads:
            self._cache_roads_to_db(roads, source="generated")
        
        return {"roads": roads, "source": "generated"}
    
    def _generate_fallback_roads(
        self,
        province: str = None,
        highway: str = None,
        condition: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Generate realistic fallback road data"""
        import random
        
        # Major Canadian highways by province
        HIGHWAYS = {
            "British Columbia": ["Trans-Canada Hwy 1", "Hwy 97", "Sea-to-Sky Hwy 99", "Hwy 3", "Hwy 5"],
            "Alberta": ["Trans-Canada Hwy 1", "Hwy 2", "Hwy 63", "Yellowhead Hwy 16", "Hwy 43"],
            "Saskatchewan": ["Trans-Canada Hwy 1", "Yellowhead Hwy 16", "Hwy 11", "Hwy 7", "Hwy 6"],
            "Manitoba": ["Trans-Canada Hwy 1", "Hwy 75", "Yellowhead Hwy 16", "Hwy 59", "Hwy 10"],
            "Ontario": ["Hwy 401", "Hwy 400", "Hwy 417", "QEW", "Hwy 11", "Trans-Canada Hwy 17"],
            "Quebec": ["Autoroute 20", "Autoroute 40", "Autoroute 10", "Autoroute 15", "Route 132"],
            "New Brunswick": ["Trans-Canada Hwy 2", "Route 1", "Route 11", "Route 7", "Route 8"],
            "Nova Scotia": ["Trans-Canada Hwy 104", "Hwy 102", "Hwy 103", "Hwy 101", "Hwy 107"],
            "Prince Edward Island": ["Trans-Canada Hwy 1", "Route 2", "Route 3", "Route 6"],
            "Newfoundland and Labrador": ["Trans-Canada Hwy 1", "Route 510", "Route 430", "Route 340"],
        }
        
        # Province centers for coordinates
        PROVINCE_CENTERS = {
            "British Columbia": (53.7267, -127.6476),
            "Alberta": (53.9333, -116.5765),
            "Saskatchewan": (52.9399, -106.4509),
            "Manitoba": (53.7609, -98.8139),
            "Ontario": (51.2538, -85.3232),
            "Quebec": (52.9399, -73.5491),
            "New Brunswick": (46.5653, -66.4619),
            "Nova Scotia": (44.6819, -63.7443),
            "Prince Edward Island": (46.2382, -63.1311),
            "Newfoundland and Labrador": (53.1355, -57.6604),
        }
        
        roads = []
        provinces = [province] if province else list(HIGHWAYS.keys())
        
        for prov in provinces:
            if prov not in HIGHWAYS:
                continue
                
            center = PROVINCE_CENTERS.get(prov, (50.0, -100.0))
            climate = PROVINCE_CLIMATE_ZONES.get(prov, ClimateZone.MODERATE)
            
            hwys = HIGHWAYS[prov]
            if highway:
                hwys = [h for h in hwys if highway.lower() in h.lower()]
            
            for hwy in hwys:
                # Generate 5-15 sections per highway
                num_sections = random.randint(5, 15)
                km_start = 0
                
                for i in range(num_sections):
                    section_length = random.uniform(5, 25)
                    km_end = km_start + section_length
                    
                    # Generate PCI with realistic distribution
                    # Weighted toward fair/good (Canadian highways generally maintained)
                    pci_roll = random.random()
                    if pci_roll < 0.25:
                        pci = random.uniform(80, 95)  # Good
                    elif pci_roll < 0.55:
                        pci = random.uniform(60, 79)  # Fair
                    elif pci_roll < 0.85:
                        pci = random.uniform(40, 59)  # Poor
                    else:
                        pci = random.uniform(20, 39)  # Critical
                    
                    cond = get_condition_label(pci)
                    
                    # Filter by condition if specified
                    if condition and cond != condition.lower():
                        km_start = km_end
                        continue
                    
                    # Generate coordinates along highway corridor
                    lat = center[0] + random.uniform(-2, 2)
                    lng = center[1] + random.uniform(-2, 2)
                    
                    # Traffic varies by highway importance
                    is_major = "Trans-Canada" in hwy or "401" in hwy or "Autoroute" in hwy
                    aadt = random.randint(15000, 80000) if is_major else random.randint(3000, 20000)
                    
                    roads.append({
                        "highway": hwy,
                        "direction": random.choice(["EB", "WB", "NB", "SB"]),
                        "section_from": f"km {km_start:.1f}",
                        "section_to": f"km {km_end:.1f}",
                        "km_start": round(km_start, 1),
                        "km_end": round(km_end, 1),
                        "pci": round(pci, 1),
                        "condition": cond,
                        "dmi": round(random.uniform(0, 100 - pci), 1),
                        "iri": round(random.uniform(0.8, 4.0), 2),
                        "pavement_type": random.choice(["AC", "AC", "AC", "PCC", "COMP"]),
                        "functional_class": "arterial" if is_major else "collector",
                        "province": prov,
                        "lat": round(lat, 6),
                        "lng": round(lng, 6),
                        "aadt": aadt,
                        "pavement_age": random.randint(3, 25),
                    })
                    
                    km_start = km_end
                    
                    if len(roads) >= limit:
                        break
                
                if len(roads) >= limit:
                    break
            
            if len(roads) >= limit:
                break
        
        return roads[:limit]
    
    def forecast_degradation(
        self,
        highway: str,
        province: str,
        years: int = 10
    ) -> List[DegradationForecast]:
        """
        Generate degradation forecasts for all sections of a highway.
        """
        # Get current road data
        road_data = self.get_road_conditions(province=province, highway=highway, limit=200)
        roads = road_data.get("roads", [])
        
        if not roads:
            return []
        
        climate_zone = PROVINCE_CLIMATE_ZONES.get(province, ClimateZone.MODERATE)
        forecasts = []
        
        for road in roads:
            current_pci = road.get("pci") or 70
            pavement_type = road.get("pavement_type") or "AC"
            aadt = road.get("aadt") or 15000
            pavement_age = road.get("pavement_age") or 10
            section = f"{road.get('section_from', '')} - {road.get('section_to', '')}"
            
            # Calculate forecast
            pci_forecast = forecast_pci(
                current_pci, years, pavement_type, climate_zone, aadt, pavement_age
            )
            
            # Find when PCI hits critical (40)
            years_to_critical = years + 1
            for year, pci in pci_forecast.items():
                if pci < 40:
                    years_to_critical = year
                    break
            
            # Find optimal intervention
            opt_year, opt_pci, cost_now, cost_opt, cost_delayed = find_optimal_intervention(
                pci_forecast, current_pci
            )
            
            # Calculate degradation rate
            rate = calculate_degradation_rate(
                current_pci, pavement_type, climate_zone, aadt, pavement_age
            )
            
            forecasts.append(DegradationForecast(
                highway=road.get("highway", highway),
                section=section,
                current_pci=current_pci,
                predicted_pci=pci_forecast,
                years_to_critical=years_to_critical,
                optimal_intervention_year=opt_year,
                optimal_intervention_pci=round(opt_pci, 1),
                estimated_cost_now=round(cost_now, 0),
                estimated_cost_optimal=round(cost_opt, 0),
                estimated_cost_delayed=round(cost_delayed, 0),
                cost_savings_optimal=round(cost_delayed - cost_opt, 0),
                degradation_rate=round(rate, 2)
            ))
        
        return forecasts
    
    def get_economic_impact(
        self,
        province: str = None,
        highway: str = None,
        condition: str = None,
        limit: int = 2000
    ) -> List[EconomicImpact]:
        """
        Calculate economic impact of road conditions.
        """
        road_data = self.get_road_conditions(
            province=province, highway=highway, condition=condition, limit=limit
        )
        roads = road_data.get("roads", [])
        
        impacts = []
        for road in roads:
            pci = road.get("pci") or 70
            aadt = road.get("aadt") or 15000
            km_start = road.get("km_start") or 0
            km_end = road.get("km_end") or 10
            section_length = abs(km_end - km_start) if km_end and km_start else 5.0
            if section_length == 0:
                section_length = 5.0  # Default 5km if same start/end
            
            impact_data = calculate_economic_impact(
                pci, aadt, section_length, road.get("functional_class") or "arterial"
            )
            
            section = f"{road.get('section_from', '')} - {road.get('section_to', '')}"
            
            impacts.append(EconomicImpact(
                highway=road.get("highway", "Unknown"),
                section=section,
                pci=pci,
                condition=road.get("condition") or get_condition_label(pci),
                daily_traffic=aadt,
                annual_vehicle_damage_cost=impact_data["vehicle_damage_cost"],
                annual_fuel_waste_cost=impact_data["fuel_waste_cost"],
                annual_freight_delay_cost=impact_data["freight_delay_cost"],
                total_annual_cost=impact_data["total_annual_cost"],
                roi_if_repaired=impact_data["roi_if_repaired"]
            ))
        
        return impacts
    
    def get_network_heatmap_data(
        self,
        province: str = None,
        min_pci: float = None,
        max_pci: float = None
    ) -> Dict[str, Any]:
        """
        Get data formatted for highway network heatmap visualization.
        """
        road_data = self.get_road_conditions(province=province, limit=500)
        roads = road_data.get("roads", [])
        
        if min_pci is not None:
            roads = [r for r in roads if r.get("pci", 100) >= min_pci]
        if max_pci is not None:
            roads = [r for r in roads if r.get("pci", 0) <= max_pci]
        
        # Format for map visualization
        segments = []
        for road in roads:
            pci = road.get("pci", 70)
            aadt = road.get("aadt", 15000)
            
            # Color coding by PCI
            if pci >= 80:
                color = "#22c55e"  # Green - good
            elif pci >= 60:
                color = "#f59e0b"  # Yellow - fair
            elif pci >= 40:
                color = "#f97316"  # Orange - poor
            else:
                color = "#ef4444"  # Red - critical
            
            # Line weight by traffic volume
            weight = min(8, max(2, aadt / 10000))
            
            segments.append({
                "highway": road.get("highway"),
                "section": f"{road.get('section_from', '')} - {road.get('section_to', '')}",
                "lat": road.get("lat"),
                "lng": road.get("lng"),
                "pci": pci,
                "condition": road.get("condition"),
                "aadt": aadt,
                "color": color,
                "weight": round(weight, 1),
                "province": road.get("province"),
                "pavement_type": road.get("pavement_type"),
            })
        
        # Summary statistics
        total = len(segments)
        by_condition = {
            "good": len([s for s in segments if s["pci"] >= 80]),
            "fair": len([s for s in segments if 60 <= s["pci"] < 80]),
            "poor": len([s for s in segments if 40 <= s["pci"] < 60]),
            "critical": len([s for s in segments if s["pci"] < 40]),
        }
        
        return {
            "segments": segments,
            "total": total,
            "by_condition": by_condition,
            "source": road_data.get("source", "unknown"),
        }


# Singleton instance
_road_service: Optional[RoadDegradationService] = None


def get_road_degradation_service() -> RoadDegradationService:
    """Get or create the road degradation service singleton"""
    global _road_service
    if _road_service is None:
        _road_service = RoadDegradationService()
    return _road_service
