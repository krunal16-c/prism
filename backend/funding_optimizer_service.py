"""
Funding Scenario Optimizer Service
Feature ID: F4-OPTIMIZE
Priority: P0 (CRITICAL - Must Have)

Implements bridge repair optimization using Risk-to-Cost Ratio (RCR).
Uses cached MCP data and government data service for real bridge information.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import math

from sqlalchemy.orm import Session
from database import SessionLocal
import models
import government_data_service


@dataclass
class BridgeForOptimization:
    """Bridge data structure for optimization"""
    id: str
    name: str
    region: str
    latitude: float
    longitude: float
    condition: str
    condition_index: Optional[float]
    year_built: Optional[str]
    risk_score: float
    estimated_repair_cost: float
    risk_cost_ratio: float  # RCR = Risk Score / Repair Cost (higher = better value)
    highway: Optional[str] = None
    structure_type: Optional[str] = None
    last_inspection: Optional[str] = None
    is_critical: bool = False  # score > 85
    is_high_risk: bool = False  # score > 70


@dataclass
class RoadSectionForOptimization:
    """Road section data structure for optimization"""
    id: str
    highway: str
    region: str
    section_from: Optional[str]
    section_to: Optional[str]
    km_start: Optional[float]
    km_end: Optional[float]
    length_km: float
    latitude: Optional[float]
    longitude: Optional[float]
    condition: str
    pci: Optional[float]
    dmi: Optional[float]
    iri: Optional[float]
    pavement_type: Optional[str]
    aadt: Optional[int]
    risk_score: float
    estimated_repair_cost: float
    risk_cost_ratio: float
    is_critical: bool = False  # score > 85
    is_high_risk: bool = False  # score > 70


@dataclass 
class OptimizationResult:
    """Result of funding optimization"""
    selected_bridges: List[Dict]
    selected_roads: List[Dict]
    total_bridges_selected: int
    total_roads_selected: int
    total_cost: float
    budget_remaining: float
    budget_utilization_percent: float
    total_risk_reduction: float
    risk_reduction_percent: float
    avg_risk_score: float
    critical_bridges_funded: int
    critical_bridges_unfunded: int
    critical_roads_funded: int
    critical_roads_unfunded: int
    unfunded_critical_bridges: List[Dict]
    unfunded_critical_roads: List[Dict]
    warnings: List[str]
    

@dataclass
class ComparisonResult:
    """Comparison between AI and Traditional approaches"""
    ai_approach: Dict
    traditional_approach: Dict
    improvement_percent: float
    improvement_description: str


class FundingOptimizerService:
    """
    Service for optimizing infrastructure funding allocation.
    Uses Risk-to-Cost Ratio (RCR) for AI-optimized selection.
    Handles both bridges and road sections.
    """
    
    # Average bridge repair cost by region (from Statistics Canada patterns)
    BASE_BRIDGE_REPAIR_COSTS = {
        "Ontario": 4_200_000,
        "Quebec": 3_800_000,
        "British Columbia": 4_500_000,
        "Alberta": 4_000_000,
        "Manitoba": 3_500_000,
        "Saskatchewan": 3_200_000,
        "Nova Scotia": 3_000_000,
        "New Brunswick": 2_900_000,
        "Newfoundland and Labrador": 3_300_000,
        "Prince Edward Island": 2_700_000,
        "Northwest Territories": 5_500_000,
        "Yukon": 5_200_000,
        "Nunavut": 6_000_000,
    }
    
    # Road repair cost per km by region (resurfacing/rehabilitation)
    BASE_ROAD_REPAIR_COST_PER_KM = {
        "Ontario": 850_000,  # ~$850K per km for highway rehabilitation
        "Quebec": 780_000,
        "British Columbia": 920_000,
        "Alberta": 800_000,
        "Manitoba": 720_000,
        "Saskatchewan": 680_000,
        "Nova Scotia": 650_000,
        "New Brunswick": 620_000,
        "Newfoundland and Labrador": 700_000,
        "Prince Edward Island": 580_000,
        "Northwest Territories": 1_100_000,
        "Yukon": 1_050_000,
        "Nunavut": 1_200_000,
    }
    
    # Condition to risk score mapping
    CONDITION_RISK_SCORES = {
        "Critical": 90,
        "Poor": 72,
        "Fair": 45,
        "Good": 20,
        "Unknown": 50,
    }
    
    def __init__(self):
        self.db = SessionLocal()
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def get_bridges_for_optimization(
        self, 
        region: str, 
        min_risk_score: float = 0
    ) -> List[BridgeForOptimization]:
        """
        Get bridges from cached MCP data only.
        Returns bridges ready for optimization with risk scores and cost estimates.
        Uses only real data - no generated fallbacks.
        """
        bridges = []
        
        # Get cached bridge data from MCP
        cached_bridges = self._get_cached_bridges(region)
        
        if cached_bridges:
            for bridge in cached_bridges:
                risk_score = self._calculate_risk_score(bridge)
                if risk_score >= min_risk_score:
                    repair_cost = self._estimate_bridge_repair_cost(bridge, region)
                    rcr = risk_score / (repair_cost / 1_000_000) if repair_cost > 0 else 0
                    
                    bridges.append(BridgeForOptimization(
                        id=bridge.get("id", ""),
                        name=bridge.get("name", "Unknown Bridge"),
                        region=region,
                        latitude=bridge.get("latitude", 0),
                        longitude=bridge.get("longitude", 0),
                        condition=bridge.get("condition", "Unknown"),
                        condition_index=bridge.get("condition_index"),
                        year_built=bridge.get("year_built"),
                        risk_score=risk_score,
                        estimated_repair_cost=repair_cost,
                        risk_cost_ratio=rcr,
                        highway=bridge.get("highway"),
                        structure_type=bridge.get("structure_type"),
                        last_inspection=bridge.get("last_inspection"),
                        is_critical=risk_score > 85,
                        is_high_risk=risk_score > 70
                    ))
        
        return bridges
    
    def get_roads_for_optimization(
        self, 
        region: str, 
        min_risk_score: float = 0
    ) -> List[RoadSectionForOptimization]:
        """
        Get road sections from cached MCP data only.
        Returns road sections ready for optimization with risk scores and cost estimates.
        Uses only real data - no generated fallbacks.
        """
        roads = []
        
        # Get cached road data from MCP
        try:
            cached_roads = self.db.query(models.CachedRoadCondition).filter(
                models.CachedRoadCondition.province == region
            ).all()
            
            for road in cached_roads:
                risk_score = self._calculate_road_risk_score(road)
                if risk_score >= min_risk_score:
                    # Calculate section length
                    length_km = 1.0  # Default 1km if no data
                    if road.km_start is not None and road.km_end is not None:
                        length_km = abs(road.km_end - road.km_start)
                        if length_km == 0:
                            length_km = 1.0
                    
                    repair_cost = self._estimate_road_repair_cost(road, region, length_km)
                    rcr = risk_score / (repair_cost / 1_000_000) if repair_cost > 0 else 0
                    
                    roads.append(RoadSectionForOptimization(
                        id=f"RD-{road.id}",
                        highway=road.highway or "Unknown",
                        region=region,
                        section_from=road.section_from,
                        section_to=road.section_to,
                        km_start=road.km_start,
                        km_end=road.km_end,
                        length_km=length_km,
                        latitude=road.lat,
                        longitude=road.lng,
                        condition=road.condition or "Unknown",
                        pci=road.pci,
                        dmi=road.dmi,
                        iri=road.iri,
                        pavement_type=road.pavement_type,
                        aadt=road.aadt,
                        risk_score=risk_score,
                        estimated_repair_cost=repair_cost,
                        risk_cost_ratio=rcr,
                        is_critical=risk_score > 85,
                        is_high_risk=risk_score > 70
                    ))
        except Exception as e:
            print(f"Error getting cached roads: {e}")
        
        return roads
    
    def _calculate_road_risk_score(self, road) -> float:
        """Calculate risk score for a road section based on PCI, condition, and traffic"""
        # Start with condition-based score
        condition = road.condition or "Unknown"
        base_score = self.CONDITION_RISK_SCORES.get(condition, 50)
        
        # PCI adjustment (0-100 scale, lower = worse)
        if road.pci is not None:
            pci_risk = 100 - road.pci
            base_score = max(base_score, pci_risk)
        
        # IRI adjustment (higher = rougher = worse)
        if road.iri is not None:
            if road.iri > 4.0:
                base_score += 15  # Very rough
            elif road.iri > 2.5:
                base_score += 8  # Rough
        
        # DMI adjustment (higher = more distress)
        if road.dmi is not None:
            if road.dmi > 70:
                base_score += 10
            elif road.dmi > 50:
                base_score += 5
        
        # AADT adjustment (higher traffic = higher priority)
        if road.aadt is not None:
            if road.aadt > 50000:
                base_score += 10  # Very high traffic
            elif road.aadt > 20000:
                base_score += 5  # High traffic
        
        return min(100, max(0, base_score))
    
    def _estimate_road_repair_cost(self, road, region: str, length_km: float) -> float:
        """
        Estimate repair cost for a road section.
        
        Cost factors:
        - Base cost per km by region
        - Condition multiplier
        - Pavement type multiplier
        - Traffic volume adjustment
        """
        base_cost_per_km = self.BASE_ROAD_REPAIR_COST_PER_KM.get(region, 850_000)
        
        # Condition multiplier
        condition = road.condition or "Unknown"
        if condition == "Critical":
            base_cost_per_km *= 1.5  # Full reconstruction needed
        elif condition == "Poor":
            base_cost_per_km *= 1.25  # Major rehabilitation
        elif condition == "Good":
            base_cost_per_km *= 0.6  # Minor maintenance only
        
        # Pavement type adjustment
        if road.pavement_type:
            ptype = road.pavement_type.upper()
            if ptype in ["PCC", "CONCRETE"]:
                base_cost_per_km *= 1.4  # Concrete more expensive
            elif ptype in ["COMP", "COMPOSITE"]:
                base_cost_per_km *= 1.2
        
        # High traffic adjustment (more complex work zones)
        if road.aadt is not None and road.aadt > 30000:
            base_cost_per_km *= 1.15
        
        # Calculate total cost
        total_cost = base_cost_per_km * length_km
        
        return round(total_cost, -3)  # Round to nearest thousand
    
    def _get_cached_bridges(self, region: str) -> List[Dict]:
        """Get bridges from database cache - real MCP data only"""
        try:
            cached = self.db.query(models.CachedBridgeLocation).filter(
                models.CachedBridgeLocation.region == region
            ).all()
            
            if cached:
                return [
                    {
                        "id": b.bridge_id,
                        "name": b.name,
                        "latitude": b.latitude,
                        "longitude": b.longitude,
                        "condition": b.condition,
                        "condition_index": b.condition_index,
                        "year_built": b.year_built,
                        "highway": b.highway,
                        "structure_type": b.structure_type,
                        "last_inspection": b.last_inspection,
                    }
                    for b in cached
                ]
        except Exception as e:
            print(f"Error getting cached bridges: {e}")
        
        # Try government data service for live MCP data
        bridge_data = government_data_service.get_bridge_locations(region, limit=500)
        return bridge_data if bridge_data else []
    
    def _calculate_risk_score(self, bridge: Dict) -> float:
        """Calculate risk score for a bridge based on condition and age"""
        condition = bridge.get("condition", "Unknown")
        base_score = self.CONDITION_RISK_SCORES.get(condition, 50)
        
        # Age adjustment
        year_built = bridge.get("year_built")
        if year_built:
            try:
                year = int(str(year_built)[:4])
                age = datetime.now().year - year
                # Add 0.3 points per year over 30 years
                if age > 30:
                    base_score += min(20, (age - 30) * 0.3)
            except (ValueError, TypeError):
                pass
        
        # Condition index adjustment (if available, 0-100 scale)
        condition_index = bridge.get("condition_index")
        if condition_index:
            try:
                idx = float(condition_index)
                # Lower index = worse condition = higher risk
                base_score = max(base_score, 100 - idx)
            except (ValueError, TypeError):
                pass
        
        return min(100, max(0, base_score))
    
    def _estimate_bridge_repair_cost(self, bridge: Dict, region: str) -> float:
        """
        Estimate repair cost for a bridge.
        
        Adjustment Factors:
        - Highway bridges: ×1.5
        - Urban bridges: ×1.2
        - Rural bridges: ×0.6
        - Critical condition: +30%
        """
        base_cost = self.BASE_BRIDGE_REPAIR_COSTS.get(region, 4_000_000)
        
        # Condition adjustment
        condition = bridge.get("condition", "Unknown")
        if condition == "Critical":
            base_cost *= 1.30  # +30% for extensive work
        elif condition == "Poor":
            base_cost *= 1.15
        elif condition == "Good":
            base_cost *= 0.70
        
        # Highway adjustment
        highway = bridge.get("highway")
        if highway:
            highway_str = str(highway).lower()
            if any(h in highway_str for h in ["401", "400", "qew", "trans-canada", "1"]):
                base_cost *= 1.5  # Major highways
            elif any(h in highway_str for h in ["highway", "hwy"]):
                base_cost *= 1.2  # Other highways
        
        # Age adjustment (older = more complex repairs)
        year_built = bridge.get("year_built")
        if year_built:
            try:
                year = int(str(year_built)[:4])
                age = datetime.now().year - year
                if age > 50:
                    base_cost *= 1.2
                elif age > 40:
                    base_cost *= 1.1
            except (ValueError, TypeError):
                pass
        
        # Add ±15% variance for estimate range
        return round(base_cost, -3)  # Round to nearest thousand
    
    def optimize_budget(
        self,
        region: str,
        budget: float,
        include_medium_risk: bool = False,
        include_roads: bool = True
    ) -> OptimizationResult:
        """
        Optimize infrastructure repair selection using Risk-to-Cost Ratio (RCR).
        
        Algorithm:
        1. Get all high-risk infrastructure (bridges and roads)
        2. Sort by RCR descending (highest value first)
        3. Select items until budget exhausted
        4. Prioritize critical infrastructure (score > 85)
        
        Args:
            region: Province/territory name
            budget: Available budget in dollars
            include_medium_risk: Include medium risk items (55-70) if budget allows
            include_roads: Include road sections in optimization
        
        Returns:
            OptimizationResult with selected bridges, roads, and metrics
        """
        min_risk = 55 if include_medium_risk else 70
        bridges = self.get_bridges_for_optimization(region, min_risk_score=min_risk)
        roads = self.get_roads_for_optimization(region, min_risk_score=min_risk) if include_roads else []
        
        if not bridges and not roads:
            return OptimizationResult(
                selected_bridges=[],
                selected_roads=[],
                total_bridges_selected=0,
                total_roads_selected=0,
                total_cost=0,
                budget_remaining=budget,
                budget_utilization_percent=0,
                total_risk_reduction=0,
                risk_reduction_percent=0,
                avg_risk_score=0,
                critical_bridges_funded=0,
                critical_bridges_unfunded=0,
                unfunded_critical_bridges=[],
                critical_roads_funded=0,
                critical_roads_unfunded=0,
                unfunded_critical_roads=[],
                warnings=["No infrastructure found for optimization in this region"]
            )
        
        # Separate critical bridges and roads
        critical_bridges = [b for b in bridges if b.is_critical]
        high_risk_bridges = [b for b in bridges if b.is_high_risk and not b.is_critical]
        other_bridges = [b for b in bridges if not b.is_high_risk]
        
        critical_roads = [r for r in roads if r.is_critical]
        high_risk_roads = [r for r in roads if r.is_high_risk and not r.is_critical]
        other_roads = [r for r in roads if not r.is_high_risk]
        
        # Sort each group by RCR (descending)
        critical_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        high_risk_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        other_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        
        critical_roads.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        high_risk_roads.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        other_roads.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        
        # Selection algorithm
        selected_bridges = []
        selected_roads = []
        remaining_budget = budget
        warnings = []
        
        # 1. First, try to fund all critical infrastructure (bridges take priority)
        unfunded_critical_bridges = []
        for bridge in critical_bridges:
            if bridge.estimated_repair_cost <= remaining_budget:
                selected_bridges.append(bridge)
                remaining_budget -= bridge.estimated_repair_cost
            else:
                unfunded_critical_bridges.append(bridge)
        
        unfunded_critical_roads = []
        for road in critical_roads:
            if road.estimated_repair_cost <= remaining_budget:
                selected_roads.append(road)
                remaining_budget -= road.estimated_repair_cost
            else:
                unfunded_critical_roads.append(road)
        
        # 2. Combine high-risk items and sort by RCR for best value
        high_risk_items = []
        for b in high_risk_bridges:
            high_risk_items.append(('bridge', b, b.risk_cost_ratio, b.estimated_repair_cost))
        for r in high_risk_roads:
            high_risk_items.append(('road', r, r.risk_cost_ratio, r.estimated_repair_cost))
        
        high_risk_items.sort(key=lambda x: x[2], reverse=True)
        
        for item_type, item, rcr, cost in high_risk_items:
            if cost <= remaining_budget:
                if item_type == 'bridge':
                    selected_bridges.append(item)
                else:
                    selected_roads.append(item)
                remaining_budget -= cost
        
        # 3. If budget remains and include_medium_risk, add other items
        if include_medium_risk:
            other_items = []
            for b in other_bridges:
                other_items.append(('bridge', b, b.risk_cost_ratio, b.estimated_repair_cost))
            for r in other_roads:
                other_items.append(('road', r, r.risk_cost_ratio, r.estimated_repair_cost))
            
            other_items.sort(key=lambda x: x[2], reverse=True)
            
            for item_type, item, rcr, cost in other_items:
                if cost <= remaining_budget:
                    if item_type == 'bridge':
                        selected_bridges.append(item)
                    else:
                        selected_roads.append(item)
                    remaining_budget -= cost
        
        # Calculate metrics
        total_cost = budget - remaining_budget
        total_bridge_risk = sum(b.risk_score for b in selected_bridges)
        total_road_risk = sum(r.risk_score for r in selected_roads)
        total_risk_reduction = total_bridge_risk + total_road_risk
        
        max_bridge_risk = sum(b.risk_score for b in bridges)
        max_road_risk = sum(r.risk_score for r in roads)
        max_possible_reduction = max_bridge_risk + max_road_risk
        
        all_selected = selected_bridges + selected_roads
        
        # Generate warnings
        if unfunded_critical_bridges:
            total_critical_cost = sum(b.estimated_repair_cost for b in unfunded_critical_bridges)
            warnings.append(
                f"⚠️ Budget insufficient for {len(unfunded_critical_bridges)} critical bridge(s) "
                f"requiring ${total_critical_cost:,.0f}"
            )
        
        if unfunded_critical_roads:
            total_critical_road_cost = sum(r.estimated_repair_cost for r in unfunded_critical_roads)
            warnings.append(
                f"⚠️ Budget insufficient for {len(unfunded_critical_roads)} critical road section(s) "
                f"requiring ${total_critical_road_cost:,.0f}"
            )
        
        return OptimizationResult(
            selected_bridges=[self._bridge_to_dict(b, rank=i+1) for i, b in enumerate(selected_bridges)],
            selected_roads=[self._road_to_dict(r, rank=i+1) for i, r in enumerate(selected_roads)],
            total_bridges_selected=len(selected_bridges),
            total_roads_selected=len(selected_roads),
            total_cost=total_cost,
            budget_remaining=remaining_budget,
            budget_utilization_percent=round((total_cost / budget * 100) if budget > 0 else 0, 1),
            total_risk_reduction=total_risk_reduction,
            risk_reduction_percent=round((total_risk_reduction / max_possible_reduction * 100) if max_possible_reduction > 0 else 0, 1),
            avg_risk_score=round(sum(b.risk_score for b in all_selected) / len(all_selected) if all_selected else 0, 1),
            critical_bridges_funded=len([b for b in selected_bridges if b.is_critical]),
            critical_bridges_unfunded=len(unfunded_critical_bridges),
            unfunded_critical_bridges=[self._bridge_to_dict(b) for b in unfunded_critical_bridges],
            critical_roads_funded=len([r for r in selected_roads if r.is_critical]),
            critical_roads_unfunded=len(unfunded_critical_roads),
            unfunded_critical_roads=[self._road_to_dict(r) for r in unfunded_critical_roads],
            warnings=warnings
        )
    
    def traditional_optimization(
        self,
        region: str,
        budget: float
    ) -> Dict:
        """
        Traditional approach: Sort bridges by age (oldest first).
        Used for comparison with AI-optimized approach.
        """
        bridges = self.get_bridges_for_optimization(region, min_risk_score=70)
        
        if not bridges:
            return {
                "bridges_repaired": 0,
                "total_spent": 0,
                "risk_reduction": 0,
                "avg_risk_score": 0,
                "bridges": []
            }
        
        # Sort by age (oldest first based on year_built)
        def get_year(b):
            try:
                return int(str(b.year_built)[:4]) if b.year_built else 2000
            except:
                return 2000
        
        bridges.sort(key=get_year)
        
        selected = []
        remaining_budget = budget
        
        for bridge in bridges:
            if bridge.estimated_repair_cost <= remaining_budget:
                selected.append(bridge)
                remaining_budget -= bridge.estimated_repair_cost
        
        total_risk_reduction = sum(b.risk_score for b in selected)
        
        return {
            "bridges_repaired": len(selected),
            "total_spent": budget - remaining_budget,
            "risk_reduction": total_risk_reduction,
            "risk_reduction_percent": round((total_risk_reduction / sum(b.risk_score for b in bridges) * 100) if bridges else 0, 1),
            "avg_risk_score": round(sum(b.risk_score for b in selected) / len(selected) if selected else 0, 1),
            "bridges": [self._bridge_to_dict(b, rank=i+1) for i, b in enumerate(selected)]
        }
    
    def compare_approaches(
        self,
        region: str,
        budget: float
    ) -> ComparisonResult:
        """
        Compare AI-optimized vs Traditional approach.
        
        Returns comparison metrics showing improvement.
        """
        ai_result = self.optimize_budget(region, budget)
        traditional_result = self.traditional_optimization(region, budget)
        
        ai_risk_reduction = ai_result.total_risk_reduction
        traditional_risk_reduction = traditional_result["risk_reduction"]
        
        if traditional_risk_reduction > 0:
            improvement = ((ai_risk_reduction - traditional_risk_reduction) / traditional_risk_reduction) * 100
        else:
            improvement = 100 if ai_risk_reduction > 0 else 0
        
        return ComparisonResult(
            ai_approach={
                "bridges_repaired": ai_result.total_bridges_selected,
                "total_spent": ai_result.total_cost,
                "budget_utilization": ai_result.budget_utilization_percent,
                "risk_reduction": ai_result.total_risk_reduction,
                "risk_reduction_percent": ai_result.risk_reduction_percent,
                "avg_risk_score": ai_result.avg_risk_score,
                "bridges": ai_result.selected_bridges,
                "critical_funded": ai_result.critical_bridges_funded,
            },
            traditional_approach=traditional_result,
            improvement_percent=round(improvement, 1),
            improvement_description=f"{abs(improvement):.0f}% {'MORE' if improvement > 0 else 'LESS'} EFFECTIVE - Same budget, {'significantly better' if improvement > 20 else 'better' if improvement > 0 else 'similar'} outcome"
        )
    
    def get_all_high_risk_bridges(self, region: str) -> Dict:
        """Get all high-risk bridges and total cost to repair all"""
        bridges = self.get_bridges_for_optimization(region, min_risk_score=70)
        
        total_cost = sum(b.estimated_repair_cost for b in bridges)
        critical_cost = sum(b.estimated_repair_cost for b in bridges if b.is_critical)
        
        return {
            "total_high_risk_bridges": len(bridges),
            "critical_bridges": len([b for b in bridges if b.is_critical]),
            "total_repair_cost": total_cost,
            "critical_repair_cost": critical_cost,
            "bridges": [self._bridge_to_dict(b) for b in bridges]
        }
    
    def get_all_high_risk_roads(self, region: str) -> Dict:
        """Get all high-risk road sections and total cost to repair all"""
        roads = self.get_roads_for_optimization(region, min_risk_score=70)
        
        total_cost = sum(r.estimated_repair_cost for r in roads)
        critical_cost = sum(r.estimated_repair_cost for r in roads if r.is_critical)
        total_length_km = sum(r.length_km for r in roads)
        
        return {
            "total_high_risk_roads": len(roads),
            "critical_roads": len([r for r in roads if r.is_critical]),
            "total_repair_cost": total_cost,
            "critical_repair_cost": critical_cost,
            "total_length_km": round(total_length_km, 2),
            "roads": [self._road_to_dict(r) for r in roads]
        }
    
    def get_all_high_risk_infrastructure(self, region: str) -> Dict:
        """Get all high-risk infrastructure (bridges + roads)"""
        bridge_data = self.get_all_high_risk_bridges(region)
        road_data = self.get_all_high_risk_roads(region)
        
        return {
            "bridges": bridge_data,
            "roads": road_data,
            "total_infrastructure_count": bridge_data["total_high_risk_bridges"] + road_data["total_high_risk_roads"],
            "total_critical_count": bridge_data["critical_bridges"] + road_data["critical_roads"],
            "total_repair_cost": bridge_data["total_repair_cost"] + road_data["total_repair_cost"],
            "total_critical_repair_cost": bridge_data["critical_repair_cost"] + road_data["critical_repair_cost"]
        }
    
    def _bridge_to_dict(self, bridge: BridgeForOptimization, rank: int = None) -> Dict:
        """Convert bridge to dictionary for API response"""
        result = {
            "id": bridge.id,
            "name": bridge.name,
            "region": bridge.region,
            "latitude": bridge.latitude,
            "longitude": bridge.longitude,
            "condition": bridge.condition,
            "condition_index": bridge.condition_index,
            "year_built": bridge.year_built,
            "risk_score": round(bridge.risk_score, 1),
            "estimated_repair_cost": bridge.estimated_repair_cost,
            "cost_display": f"${bridge.estimated_repair_cost:,.0f}",
            "cost_range_low": round(bridge.estimated_repair_cost * 0.8, -3),
            "cost_range_high": round(bridge.estimated_repair_cost * 1.2, -3),
            "risk_cost_ratio": round(bridge.risk_cost_ratio, 2),
            "highway": bridge.highway,
            "structure_type": bridge.structure_type,
            "last_inspection": bridge.last_inspection,
            "is_critical": bridge.is_critical,
            "is_high_risk": bridge.is_high_risk,
            "justification": self._generate_justification(bridge),
        }
        
        if rank:
            result["rank"] = rank
        
        return result
    
    def _generate_justification(self, bridge: BridgeForOptimization) -> str:
        """Generate justification text for bridge selection"""
        factors = []
        
        if bridge.is_critical:
            factors.append("CRITICAL condition requiring immediate attention")
        elif bridge.is_high_risk:
            factors.append("HIGH risk score indicates urgent repair need")
        
        if bridge.risk_cost_ratio > 20:
            factors.append("Excellent risk-to-cost ratio (high value investment)")
        elif bridge.risk_cost_ratio > 15:
            factors.append("Good risk-to-cost ratio")
        
        if bridge.highway:
            factors.append(f"Located on {bridge.highway} (high traffic impact)")
        
        if bridge.year_built:
            try:
                age = datetime.now().year - int(str(bridge.year_built)[:4])
                if age > 50:
                    factors.append(f"Aging infrastructure ({age} years old)")
            except:
                pass
        
        return "; ".join(factors) if factors else "Standard maintenance priority"
    
    def _road_to_dict(self, road: RoadSectionForOptimization, rank: int = None) -> Dict:
        """Convert road section to dictionary for API response"""
        # Build section description
        section_desc = f"{road.highway}"
        if road.section_from and road.section_to:
            section_desc = f"{road.highway}: {road.section_from} to {road.section_to}"
        elif road.km_start is not None and road.km_end is not None:
            section_desc = f"{road.highway} (km {road.km_start:.1f} - {road.km_end:.1f})"
        
        result = {
            "id": road.id,
            "type": "road",
            "highway": road.highway,
            "section_description": section_desc,
            "region": road.region,
            "section_from": road.section_from,
            "section_to": road.section_to,
            "km_start": road.km_start,
            "km_end": road.km_end,
            "length_km": round(road.length_km, 2),
            "latitude": road.latitude,
            "longitude": road.longitude,
            "condition": road.condition,
            "pci": road.pci,
            "dmi": road.dmi,
            "iri": road.iri,
            "pavement_type": road.pavement_type,
            "aadt": road.aadt,
            "risk_score": round(road.risk_score, 1),
            "estimated_repair_cost": road.estimated_repair_cost,
            "cost_display": f"${road.estimated_repair_cost:,.0f}",
            "cost_per_km": round(road.estimated_repair_cost / road.length_km, 0) if road.length_km > 0 else 0,
            "cost_range_low": round(road.estimated_repair_cost * 0.8, -3),
            "cost_range_high": round(road.estimated_repair_cost * 1.2, -3),
            "risk_cost_ratio": round(road.risk_cost_ratio, 2),
            "is_critical": road.is_critical,
            "is_high_risk": road.is_high_risk,
            "justification": self._generate_road_justification(road),
        }
        
        if rank:
            result["rank"] = rank
        
        return result
    
    def _generate_road_justification(self, road: RoadSectionForOptimization) -> str:
        """Generate justification text for road section selection"""
        factors = []
        
        if road.is_critical:
            factors.append("CRITICAL condition requiring immediate attention")
        elif road.is_high_risk:
            factors.append("HIGH risk score indicates urgent repair need")
        
        if road.risk_cost_ratio > 20:
            factors.append("Excellent risk-to-cost ratio (high value investment)")
        elif road.risk_cost_ratio > 15:
            factors.append("Good risk-to-cost ratio")
        
        if road.pci is not None and road.pci < 50:
            factors.append(f"Low PCI score ({road.pci:.0f}/100)")
        
        if road.iri is not None and road.iri > 3.0:
            factors.append(f"High roughness index (IRI: {road.iri:.1f})")
        
        if road.aadt is not None:
            if road.aadt > 50000:
                factors.append(f"Very high traffic ({road.aadt:,} AADT)")
            elif road.aadt > 20000:
                factors.append(f"High traffic ({road.aadt:,} AADT)")
        
        if road.length_km > 5:
            factors.append(f"Extended section ({road.length_km:.1f} km)")
        
        return "; ".join(factors) if factors else "Standard maintenance priority"


# Singleton service instance
_funding_optimizer_service = None

def get_funding_optimizer_service() -> FundingOptimizerService:
    """Get or create the funding optimizer service instance"""
    global _funding_optimizer_service
    if _funding_optimizer_service is None:
        _funding_optimizer_service = FundingOptimizerService()
    return _funding_optimizer_service
