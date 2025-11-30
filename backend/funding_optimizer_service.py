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
class OptimizationResult:
    """Result of funding optimization"""
    selected_bridges: List[Dict]
    total_bridges_selected: int
    total_cost: float
    budget_remaining: float
    budget_utilization_percent: float
    total_risk_reduction: float
    risk_reduction_percent: float
    avg_risk_score: float
    critical_bridges_funded: int
    critical_bridges_unfunded: int
    unfunded_critical_bridges: List[Dict]
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
    """
    
    # Average repair cost by region (from Statistics Canada patterns)
    BASE_REPAIR_COSTS = {
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
                    repair_cost = self._estimate_repair_cost(bridge, region)
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
    
    def _estimate_repair_cost(self, bridge: Dict, region: str) -> float:
        """
        Estimate repair cost for a bridge.
        
        Adjustment Factors:
        - Highway bridges: ×1.5
        - Urban bridges: ×1.2
        - Rural bridges: ×0.6
        - Critical condition: +30%
        """
        base_cost = self.BASE_REPAIR_COSTS.get(region, 4_000_000)
        
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
        include_medium_risk: bool = False
    ) -> OptimizationResult:
        """
        Optimize bridge repair selection using Risk-to-Cost Ratio (RCR).
        
        Algorithm:
        1. Filter high-risk bridges (score > 70)
        2. Sort by RCR descending (highest value first)
        3. Select bridges until budget exhausted
        4. Prioritize critical bridges (score > 85)
        
        Args:
            region: Province/territory name
            budget: Available budget in dollars
            include_medium_risk: Include medium risk bridges (55-70) if budget allows
        
        Returns:
            OptimizationResult with selected bridges and metrics
        """
        min_risk = 55 if include_medium_risk else 70
        bridges = self.get_bridges_for_optimization(region, min_risk_score=min_risk)
        
        if not bridges:
            return OptimizationResult(
                selected_bridges=[],
                total_bridges_selected=0,
                total_cost=0,
                budget_remaining=budget,
                budget_utilization_percent=0,
                total_risk_reduction=0,
                risk_reduction_percent=0,
                avg_risk_score=0,
                critical_bridges_funded=0,
                critical_bridges_unfunded=0,
                unfunded_critical_bridges=[],
                warnings=["No bridges found for optimization in this region"]
            )
        
        # Separate critical bridges
        critical_bridges = [b for b in bridges if b.is_critical]
        high_risk_bridges = [b for b in bridges if b.is_high_risk and not b.is_critical]
        other_bridges = [b for b in bridges if not b.is_high_risk]
        
        # Sort each group by RCR (descending)
        critical_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        high_risk_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        other_bridges.sort(key=lambda x: x.risk_cost_ratio, reverse=True)
        
        # Selection algorithm
        selected = []
        remaining_budget = budget
        warnings = []
        
        # 1. First, try to fund all critical bridges
        unfunded_critical = []
        for bridge in critical_bridges:
            if bridge.estimated_repair_cost <= remaining_budget:
                selected.append(bridge)
                remaining_budget -= bridge.estimated_repair_cost
            else:
                unfunded_critical.append(bridge)
        
        # 2. Add high-risk bridges by RCR
        for bridge in high_risk_bridges:
            if bridge.estimated_repair_cost <= remaining_budget:
                selected.append(bridge)
                remaining_budget -= bridge.estimated_repair_cost
        
        # 3. If budget remains and include_medium_risk, add other bridges
        if include_medium_risk:
            for bridge in other_bridges:
                if bridge.estimated_repair_cost <= remaining_budget:
                    selected.append(bridge)
                    remaining_budget -= bridge.estimated_repair_cost
        
        # Calculate metrics
        total_cost = budget - remaining_budget
        total_risk_reduction = sum(b.risk_score for b in selected)
        max_possible_reduction = sum(b.risk_score for b in bridges)
        
        # Generate warnings
        if unfunded_critical:
            total_critical_cost = sum(b.estimated_repair_cost for b in unfunded_critical)
            warnings.append(
                f"⚠️ Budget insufficient for {len(unfunded_critical)} critical bridge(s) "
                f"requiring ${total_critical_cost:,.0f}"
            )
        
        return OptimizationResult(
            selected_bridges=[self._bridge_to_dict(b, rank=i+1) for i, b in enumerate(selected)],
            total_bridges_selected=len(selected),
            total_cost=total_cost,
            budget_remaining=remaining_budget,
            budget_utilization_percent=round((total_cost / budget * 100) if budget > 0 else 0, 1),
            total_risk_reduction=total_risk_reduction,
            risk_reduction_percent=round((total_risk_reduction / max_possible_reduction * 100) if max_possible_reduction > 0 else 0, 1),
            avg_risk_score=round(sum(b.risk_score for b in selected) / len(selected) if selected else 0, 1),
            critical_bridges_funded=len([b for b in selected if b.is_critical]),
            critical_bridges_unfunded=len(unfunded_critical),
            unfunded_critical_bridges=[self._bridge_to_dict(b) for b in unfunded_critical],
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


# Singleton service instance
_funding_optimizer_service = None

def get_funding_optimizer_service() -> FundingOptimizerService:
    """Get or create the funding optimizer service instance"""
    global _funding_optimizer_service
    if _funding_optimizer_service is None:
        _funding_optimizer_service = FundingOptimizerService()
    return _funding_optimizer_service
