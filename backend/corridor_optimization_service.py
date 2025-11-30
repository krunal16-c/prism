"""
Corridor Optimization Service
Feature 12: Multi-Section Bundling & Directional Analysis

Optimizes road repair planning by:
- Bundling adjacent sections for cost efficiency
- Analyzing directional condition differences
- Identifying continuous corridor opportunities
- Calculating bundling savings

Uses RoadDegradationService for real data with fallback support.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

# Import RoadDegradationService for data access (handles MCP + fallback)
from road_degradation_service import RoadDegradationService


@dataclass
class RoadSection:
    """Individual road section data"""
    highway: str
    direction: str
    section_from: str
    section_to: str
    km_start: float
    km_end: float
    pci: float
    condition: str
    dmi: float
    iri: float
    pavement_type: str
    aadt: int
    
    @property
    def length_km(self) -> float:
        return abs(self.km_end - self.km_start)
    
    @property
    def needs_repair(self) -> bool:
        return self.pci < 70  # Fair or worse


@dataclass
class BundleOpportunity:
    """A bundle of adjacent sections that can be repaired together"""
    highway: str
    direction: str
    sections: List[RoadSection]
    bundle_id: str
    
    # Geometry
    start_km: float
    end_km: float
    total_length_km: float
    
    # Condition metrics
    average_pci: float
    min_pci: float
    max_pci: float
    sections_needing_repair: int
    
    # Cost analysis
    individual_cost: float
    bundled_cost: float
    savings: float
    savings_percent: float
    
    # Benefits
    traffic_disruptions_avoided: int
    mobilization_savings: float
    continuous_smooth_km: float
    
    # Funding eligibility
    qualifies_for_federal_funding: bool
    federal_funding_threshold: float


@dataclass
class DirectionalAnalysis:
    """Comparison of road condition by direction"""
    highway: str
    km_range: str
    
    # Direction 1 (e.g., Eastbound)
    direction_1: str
    direction_1_sections: int
    direction_1_avg_pci: float
    direction_1_avg_iri: float
    direction_1_avg_dmi: float
    direction_1_truck_percent: float
    
    # Direction 2 (e.g., Westbound)
    direction_2: str
    direction_2_sections: int
    direction_2_avg_pci: float
    direction_2_avg_iri: float
    direction_2_avg_dmi: float
    direction_2_truck_percent: float
    
    # Analysis
    pci_difference: float
    worse_direction: str
    degradation_reason: str
    
    # Recommendation
    recommendation: str
    single_direction_repair_cost: float
    both_directions_repair_cost: float
    potential_savings: float


@dataclass
class CorridorOptimizationSummary:
    """Summary of corridor optimization opportunities"""
    province: str
    highway: str
    
    # Bundle opportunities
    total_bundles: int
    total_sections_bundled: int
    total_bundled_length_km: float
    
    # Savings
    total_individual_cost: float
    total_bundled_cost: float
    total_savings: float
    average_savings_percent: float
    
    # Directional analysis
    directions_with_disparity: int
    single_direction_opportunities: int
    
    # Best opportunities
    top_bundle_savings: float
    top_bundle_id: str


# Cost factors
MOBILIZATION_COST = 250000  # $250K per contractor mobilization
COST_PER_KM_INDIVIDUAL = 550000  # $550K/km for individual repairs
COST_PER_KM_BUNDLED = 470000  # $470K/km for bundled repairs (economies of scale)
FEDERAL_FUNDING_THRESHOLD = 20000000  # $20M for federal infrastructure funding


def get_pci_condition(pci: float) -> str:
    """Get condition label from PCI"""
    if pci >= 80:
        return "Good"
    elif pci >= 60:
        return "Fair"
    elif pci >= 40:
        return "Poor"
    else:
        return "Critical"


def estimate_truck_percent(aadt: int, direction: str) -> float:
    """
    Estimate truck traffic percentage.
    Typically higher in directions toward industrial areas.
    """
    # Base truck percentage based on traffic volume
    if aadt >= 50000:
        base_percent = 30  # Major highway
    elif aadt >= 30000:
        base_percent = 35
    elif aadt >= 15000:
        base_percent = 40
    else:
        base_percent = 25
    
    # Direction adjustment (west/south typically has more loaded trucks in Ontario)
    direction_upper = direction.upper()
    if direction_upper in ["W", "WB", "WEST", "S", "SB", "SOUTH"]:
        return base_percent + 8  # More outbound loaded trucks
    elif direction_upper in ["E", "EB", "EAST", "N", "NB", "NORTH"]:
        return base_percent  # Returning trucks often lighter
    
    return base_percent


class CorridorOptimizationService:
    """Service for corridor-level optimization of road repairs"""
    
    def __init__(self):
        self.road_service = RoadDegradationService()
    
    def _get_road_sections(self, province: str, highway: str = None, limit: int = 200) -> List[RoadSection]:
        """Fetch and parse road sections from RoadDegradationService"""
        result = self.road_service.get_road_conditions(
            province=province,
            highway=highway,
            limit=limit
        )
        
        if not result or "roads" not in result:
            return []
        
        sections = []
        
        # Group by highway+direction for synthetic km assignment
        grouped_roads: Dict[str, List[dict]] = defaultdict(list)
        for road in result["roads"]:
            key = f"{road.get('highway', 'Unknown')}_{road.get('direction', '')}"
            grouped_roads[key].append(road)
        
        # Assign synthetic km values where missing
        for key, roads in grouped_roads.items():
            current_km = 0.0
            for road in roads:
                km_start = road.get("km_start")
                km_end = road.get("km_end")
                
                # If km values are missing, assign synthetic ones (5km per section)
                if km_start is None or km_end is None or (km_start == 0 and km_end == 0):
                    section_length = 5.0  # Assume 5km sections
                    km_start = current_km
                    km_end = current_km + section_length
                    current_km = km_end + 0.5  # Small gap between sections
                
                section = RoadSection(
                    highway=road.get("highway", "Unknown"),
                    direction=road.get("direction", ""),
                    section_from=road.get("section_from", ""),
                    section_to=road.get("section_to", ""),
                    km_start=km_start,
                    km_end=km_end,
                    pci=road.get("pci") or 70,
                    condition=get_pci_condition(road.get("pci") or 70),
                    dmi=road.get("dmi") or 10,
                    iri=road.get("iri") or 2.0,
                    pavement_type=road.get("pavement_type") or "AC",
                    aadt=road.get("aadt") or 15000
                )
                sections.append(section)
        
        return sections
    
    def find_bundle_opportunities(
        self,
        province: str,
        highway: str = None,
        min_bundle_length_km: float = 10,
        max_gap_km: float = 25
    ) -> List[BundleOpportunity]:
        """
        Find opportunities to bundle adjacent road sections for repair.
        
        Args:
            province: Province name
            highway: Optional specific highway
            min_bundle_length_km: Minimum total length for a bundle
            max_gap_km: Maximum gap between sections to still bundle
            
        Returns:
            List of bundle opportunities sorted by savings
        """
        sections = self._get_road_sections(province, highway)
        
        if not sections:
            return []
        
        # Group by highway only (combine all directions for bundling)
        grouped: Dict[str, List[RoadSection]] = defaultdict(list)
        for section in sections:
            grouped[section.highway].append(section)
        
        bundles = []
        bundle_counter = 1
        
        for hwy, section_list in grouped.items():
            # Sort by km_start
            section_list.sort(key=lambda s: s.km_start)
            
            # Find sections needing repair (PCI < 70)
            repair_sections = [s for s in section_list if s.needs_repair]
            
            if len(repair_sections) < 2:
                # Try to bundle anyway if there are multiple sections
                repair_sections = [s for s in section_list if s.pci < 80]  # Relax threshold
            
            if len(repair_sections) < 2:
                continue
            
            # Try to build bundles from adjacent repair sections
            current_bundle: List[RoadSection] = []
            
            for section in repair_sections:
                if not current_bundle:
                    current_bundle = [section]
                else:
                    last = current_bundle[-1]
                    gap = section.km_start - last.km_end
                    
                    if gap <= max_gap_km:
                        current_bundle.append(section)
                    else:
                        # Save current bundle if large enough
                        if len(current_bundle) >= 2:
                            # Get primary direction from bundle sections
                            bundle_direction = current_bundle[0].direction
                            bundle = self._create_bundle(
                                current_bundle, hwy, bundle_direction, 
                                f"B{bundle_counter:03d}"
                            )
                            if bundle.total_length_km >= min_bundle_length_km:
                                bundles.append(bundle)
                                bundle_counter += 1
                        
                        # Start new bundle
                        current_bundle = [section]
            
            # Don't forget last bundle
            if len(current_bundle) >= 2:
                bundle_direction = current_bundle[0].direction
                bundle = self._create_bundle(
                    current_bundle, hwy, bundle_direction,
                    f"B{bundle_counter:03d}"
                )
                if bundle.total_length_km >= min_bundle_length_km:
                    bundles.append(bundle)
                    bundle_counter += 1
        
        # Sort by savings descending
        bundles.sort(key=lambda b: b.savings, reverse=True)
        
        return bundles
    
    def _create_bundle(
        self, 
        sections: List[RoadSection], 
        highway: str, 
        direction: str,
        bundle_id: str
    ) -> BundleOpportunity:
        """Create a bundle opportunity from sections"""
        start_km = min(s.km_start for s in sections)
        end_km = max(s.km_end for s in sections)
        total_length = sum(s.length_km for s in sections)
        
        pcis = [s.pci for s in sections]
        avg_pci = sum(pcis) / len(pcis)
        
        # Cost calculations
        individual_cost = (
            len(sections) * MOBILIZATION_COST +  # Mobilization per section
            total_length * COST_PER_KM_INDIVIDUAL
        )
        
        bundled_cost = (
            MOBILIZATION_COST +  # Single mobilization
            total_length * COST_PER_KM_BUNDLED
        )
        
        savings = individual_cost - bundled_cost
        savings_percent = (savings / individual_cost) * 100 if individual_cost > 0 else 0
        
        # Mobilization savings
        mobilization_savings = (len(sections) - 1) * MOBILIZATION_COST
        
        # Traffic disruptions avoided (n-1 disruptions)
        traffic_disruptions_avoided = len(sections) - 1
        
        return BundleOpportunity(
            highway=highway,
            direction=direction,
            sections=sections,
            bundle_id=bundle_id,
            start_km=start_km,
            end_km=end_km,
            total_length_km=round(total_length, 1),
            average_pci=round(avg_pci, 1),
            min_pci=min(pcis),
            max_pci=max(pcis),
            sections_needing_repair=len(sections),
            individual_cost=individual_cost,
            bundled_cost=bundled_cost,
            savings=savings,
            savings_percent=round(savings_percent, 1),
            traffic_disruptions_avoided=traffic_disruptions_avoided,
            mobilization_savings=mobilization_savings,
            continuous_smooth_km=round(end_km - start_km, 1),
            qualifies_for_federal_funding=bundled_cost >= FEDERAL_FUNDING_THRESHOLD,
            federal_funding_threshold=FEDERAL_FUNDING_THRESHOLD
        )
    
    def analyze_directional_conditions(
        self,
        province: str,
        highway: str
    ) -> List[DirectionalAnalysis]:
        """
        Compare conditions between opposite directions on the same highway.
        
        Useful for identifying:
        - Heavier truck traffic in one direction
        - Different degradation patterns
        - Single-direction repair opportunities
        """
        sections = self._get_road_sections(province, highway, limit=200)
        
        if not sections:
            return []
        
        # Group by direction
        by_direction: Dict[str, List[RoadSection]] = defaultdict(list)
        for section in sections:
            by_direction[section.direction].append(section)
        
        directions = list(by_direction.keys())
        
        if len(directions) < 2:
            return []
        
        # Get the two main directions
        dir_1, dir_2 = sorted(directions, key=lambda d: len(by_direction[d]), reverse=True)[:2]
        sections_1 = by_direction[dir_1]
        sections_2 = by_direction[dir_2]
        
        # Calculate averages for each direction
        def calc_averages(secs: List[RoadSection]) -> Tuple[float, float, float, float]:
            if not secs:
                return 0, 0, 0, 0
            avg_pci = sum(s.pci for s in secs) / len(secs)
            avg_iri = sum(s.iri for s in secs) / len(secs)
            avg_dmi = sum(s.dmi for s in secs) / len(secs)
            avg_truck = sum(estimate_truck_percent(s.aadt, s.direction) for s in secs) / len(secs)
            return avg_pci, avg_iri, avg_dmi, avg_truck
        
        pci_1, iri_1, dmi_1, truck_1 = calc_averages(sections_1)
        pci_2, iri_2, dmi_2, truck_2 = calc_averages(sections_2)
        
        pci_diff = abs(pci_1 - pci_2)
        worse_dir = dir_1 if pci_1 < pci_2 else dir_2
        worse_pci = min(pci_1, pci_2)
        better_pci = max(pci_1, pci_2)
        
        # Determine degradation reason
        if pci_diff < 3:
            reason = "Similar conditions in both directions"
        elif truck_1 > truck_2 + 5 and pci_1 < pci_2:
            reason = f"Higher truck traffic ({truck_1:.0f}% vs {truck_2:.0f}%) in {dir_1} direction"
        elif truck_2 > truck_1 + 5 and pci_2 < pci_1:
            reason = f"Higher truck traffic ({truck_2:.0f}% vs {truck_1:.0f}%) in {dir_2} direction"
        else:
            reason = "Different traffic patterns or maintenance history"
        
        # Calculate costs
        worse_sections = sections_1 if pci_1 < pci_2 else sections_2
        worse_length = sum(s.length_km for s in worse_sections if s.needs_repair)
        
        single_dir_cost = worse_length * COST_PER_KM_BUNDLED + MOBILIZATION_COST
        both_dir_cost = single_dir_cost * 1.9  # Almost double for both directions
        potential_savings = both_dir_cost - single_dir_cost
        
        # Generate recommendation
        if pci_diff >= 6 and worse_pci < 65:
            recommendation = f"Prioritize {worse_dir} lane for immediate repair. Single direction saves {potential_savings/1000000:.1f}M"
        elif pci_diff >= 3:
            recommendation = f"{worse_dir} direction degrading faster. Monitor and schedule {worse_dir} first"
        else:
            recommendation = "Both directions similar. Bundle repairs when scheduling"
        
        # Determine km range
        all_sections = sections_1 + sections_2
        min_km = min(s.km_start for s in all_sections)
        max_km = max(s.km_end for s in all_sections)
        
        analysis = DirectionalAnalysis(
            highway=highway,
            km_range=f"KM {min_km:.0f}-{max_km:.0f}",
            direction_1=dir_1,
            direction_1_sections=len(sections_1),
            direction_1_avg_pci=round(pci_1, 1),
            direction_1_avg_iri=round(iri_1, 2),
            direction_1_avg_dmi=round(dmi_1, 1),
            direction_1_truck_percent=round(truck_1, 0),
            direction_2=dir_2,
            direction_2_sections=len(sections_2),
            direction_2_avg_pci=round(pci_2, 1),
            direction_2_avg_iri=round(iri_2, 2),
            direction_2_avg_dmi=round(dmi_2, 1),
            direction_2_truck_percent=round(truck_2, 0),
            pci_difference=round(pci_diff, 1),
            worse_direction=worse_dir,
            degradation_reason=reason,
            recommendation=recommendation,
            single_direction_repair_cost=single_dir_cost,
            both_directions_repair_cost=both_dir_cost,
            potential_savings=potential_savings
        )
        
        return [analysis]
    
    def get_corridor_summary(
        self,
        province: str,
        highway: str = None
    ) -> Optional[CorridorOptimizationSummary]:
        """Get summary of corridor optimization opportunities"""
        bundles = self.find_bundle_opportunities(province, highway, min_bundle_length_km=10)
        
        if not bundles:
            # Return empty summary
            return CorridorOptimizationSummary(
                province=province,
                highway=highway or "All Highways",
                total_bundles=0,
                total_sections_bundled=0,
                total_bundled_length_km=0,
                total_individual_cost=0,
                total_bundled_cost=0,
                total_savings=0,
                average_savings_percent=0,
                directions_with_disparity=0,
                single_direction_opportunities=0,
                top_bundle_savings=0,
                top_bundle_id=""
            )
        
        total_sections = sum(len(b.sections) for b in bundles)
        total_length = sum(b.total_length_km for b in bundles)
        total_individual = sum(b.individual_cost for b in bundles)
        total_bundled = sum(b.bundled_cost for b in bundles)
        total_savings = sum(b.savings for b in bundles)
        avg_savings_pct = (total_savings / total_individual * 100) if total_individual > 0 else 0
        
        # Count directional disparities
        directional_analyses = []
        if highway:
            directional_analyses = self.analyze_directional_conditions(province, highway)
        
        disparities = sum(1 for a in directional_analyses if a.pci_difference >= 5)
        single_dir_opps = sum(1 for a in directional_analyses if a.pci_difference >= 6)
        
        top_bundle = bundles[0] if bundles else None
        
        return CorridorOptimizationSummary(
            province=province,
            highway=highway or "All Highways",
            total_bundles=len(bundles),
            total_sections_bundled=total_sections,
            total_bundled_length_km=round(total_length, 1),
            total_individual_cost=total_individual,
            total_bundled_cost=total_bundled,
            total_savings=total_savings,
            average_savings_percent=round(avg_savings_pct, 1),
            directions_with_disparity=disparities,
            single_direction_opportunities=single_dir_opps,
            top_bundle_savings=top_bundle.savings if top_bundle else 0,
            top_bundle_id=top_bundle.bundle_id if top_bundle else ""
        )


# Singleton instance
_corridor_service: Optional[CorridorOptimizationService] = None


def get_corridor_service() -> CorridorOptimizationService:
    """Get or create corridor optimization service singleton"""
    global _corridor_service
    if _corridor_service is None:
        _corridor_service = CorridorOptimizationService()
    return _corridor_service
