"""
Winter Resilience Prediction Service
Feature 11: Winter Damage Forecaster

Predicts which road sections will suffer worst winter damage using:
- Freeze-thaw cycle analysis by region
- Pavement vulnerability factors
- Current PCI and crack propagation risk
- Traffic load impacts during freeze-thaw
- Drainage factors

Uses RoadDegradationService for real data with fallback support.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

# Import RoadDegradationService for data access (handles MCP + fallback)
from road_degradation_service import RoadDegradationService


class WinterRiskLevel(Enum):
    """Winter damage risk levels"""
    SEVERE = "severe"       # Expected PCI loss >10 points
    HIGH = "high"           # Expected PCI loss 7-10 points
    MODERATE = "moderate"   # Expected PCI loss 4-7 points
    LOW = "low"             # Expected PCI loss <4 points


@dataclass
class WinterVulnerability:
    """Winter vulnerability assessment for a road segment"""
    highway: str
    direction: str
    section_from: str
    section_to: str
    km_start: float
    km_end: float
    current_pci: float
    current_condition: str
    pavement_type: str
    
    # Freeze-thaw analysis
    climate_zone: str
    freeze_thaw_cycles: int
    
    # Vulnerability factors
    pci_vulnerability_factor: float
    pavement_vulnerability_factor: float
    traffic_load_factor: float
    drainage_factor: float
    
    # Predictions
    winter_damage_risk_score: float  # 0-100
    risk_level: str
    expected_pci_loss: float
    post_winter_pci: float
    post_winter_condition: str
    crosses_threshold: bool
    threshold_crossed: str  # e.g., "Fair→Poor"
    
    # Recommendations
    recommendation: str
    recommended_action: str
    pre_winter_cost: float
    spring_repair_cost: float
    cost_savings: float
    roi: float


@dataclass
class PreWinterIntervention:
    """Pre-winter intervention analysis for a road section"""
    highway: str
    section: str
    current_pci: float
    
    # Option A: Pre-winter action
    pre_winter_action: str
    pre_winter_cost: float
    pci_loss_with_action: float
    spring_pci_with_action: float
    
    # Option B: Do nothing
    pci_loss_without_action: float
    spring_pci_without_action: float
    emergency_repair_cost: float
    traffic_disruption_weeks: int
    
    # ROI analysis
    cost_savings: float
    roi_multiplier: float
    recommendation: str


@dataclass 
class WinterForecastSummary:
    """Summary of winter forecast for a highway/region"""
    province: str
    highway: str
    total_sections: int
    severe_risk_count: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int
    total_km_at_risk: float
    average_expected_pci_loss: float
    sections_crossing_threshold: int
    total_pre_winter_investment: float
    total_spring_repair_avoided: float
    total_potential_savings: float
    overall_roi: float


# Climate zone freeze-thaw data for Canadian provinces/regions
FREEZE_THAW_CYCLES: Dict[str, int] = {
    # Ontario regions
    "Northern Ontario": 52,
    "Eastern Ontario": 48,
    "Southern Ontario": 45,
    "Central Ontario": 47,
    "Ontario": 46,  # Default
    
    # Quebec regions
    "Northern Quebec": 55,
    "Quebec": 50,
    
    # Prairie provinces
    "Alberta": 42,
    "Saskatchewan": 44,
    "Manitoba": 48,
    
    # BC
    "British Columbia": 28,  # Coast average
    "Northern BC": 45,
    
    # Atlantic
    "New Brunswick": 52,
    "Nova Scotia": 48,
    "Prince Edward Island": 50,
    "Newfoundland and Labrador": 55,
    
    # Territories
    "Yukon": 35,  # Permafrost, fewer cycles
    "Northwest Territories": 32,
    "Nunavut": 28,
}

# Climate zone names by province
CLIMATE_ZONES: Dict[str, str] = {
    "Ontario": "Southern Ontario",
    "Quebec": "Quebec",
    "British Columbia": "BC Coast",
    "Alberta": "Prairie",
    "Saskatchewan": "Prairie",
    "Manitoba": "Prairie",
    "New Brunswick": "Atlantic",
    "Nova Scotia": "Atlantic",
    "Prince Edward Island": "Atlantic",
    "Newfoundland and Labrador": "Atlantic",
}

# Pavement vulnerability to freeze-thaw (1.0 = baseline)
PAVEMENT_VULNERABILITY: Dict[str, float] = {
    "AC": 1.3,      # Asphalt - most vulnerable, water infiltrates cracks
    "PCC": 0.7,     # Concrete - more resistant
    "COMP": 1.0,    # Composite - moderate
    "ST": 1.5,      # Surface treated - very vulnerable
    "GRAVEL": 0.5,  # Gravel - permeable, less freeze damage
}

# PCI vulnerability zones - roads in "vulnerable zone" degrade faster
def get_pci_vulnerability_factor(pci: float) -> float:
    """
    Roads at PCI 60-70 are in the "vulnerable zone" where cracks propagate.
    Higher PCI = less vulnerability, Lower PCI = already damaged, less to lose.
    """
    if pci >= 80:
        return 0.6  # Good condition, sealed surface
    elif pci >= 70:
        return 0.9  # Starting to show wear
    elif pci >= 60:
        return 1.4  # VULNERABLE ZONE - cracks propagate rapidly
    elif pci >= 50:
        return 1.2  # Already damaged, cracks present
    elif pci >= 40:
        return 1.0  # Poor condition
    else:
        return 0.8  # Critical - already extensively damaged


def get_traffic_load_factor(aadt: Optional[int]) -> float:
    """Traffic load impact on freeze-thaw damage"""
    if aadt is None:
        return 1.0  # Default to moderate traffic
    if aadt >= 50000:
        return 1.4  # Very heavy traffic
    elif aadt >= 30000:
        return 1.2  # Heavy traffic
    elif aadt >= 15000:
        return 1.0  # Moderate traffic
    elif aadt >= 5000:
        return 0.9  # Light traffic
    else:
        return 0.8  # Very light traffic


def get_drainage_factor(dmi: Optional[float], iri: Optional[float]) -> float:
    """
    Estimate drainage quality from DMI and IRI.
    Higher DMI/IRI = more surface distress = likely poor drainage.
    """
    dmi = dmi if dmi is not None else 10.0  # Default values
    iri = iri if iri is not None else 2.0
    distress_score = (dmi / 50) + (iri / 5)  # Normalize
    if distress_score > 1.5:
        return 1.5  # Poor drainage likely
    elif distress_score > 1.0:
        return 1.2  # Fair drainage
    elif distress_score > 0.5:
        return 1.0  # Average drainage
    else:
        return 0.8  # Good drainage


def calculate_winter_damage_risk(
    current_pci: float,
    freeze_thaw_cycles: int,
    pavement_vulnerability: float,
    traffic_load_factor: float,
    drainage_factor: float
) -> tuple[float, float]:
    """
    Calculate winter damage risk score and expected PCI loss.
    
    Formula:
    Winter_Damage_Risk = (100 - current_PCI) × 
                         freeze_thaw_cycles × 
                         pavement_vulnerability × 
                         traffic_load_factor × 
                         drainage_factor
    
    Normalized to 0-100 scale.
    """
    # Base vulnerability from current condition
    condition_vulnerability = (100 - current_pci) / 100
    
    # Freeze-thaw impact (normalized, 50 cycles = baseline)
    freeze_thaw_factor = freeze_thaw_cycles / 50
    
    # Combined risk score
    raw_risk = (
        condition_vulnerability * 
        freeze_thaw_factor * 
        pavement_vulnerability * 
        traffic_load_factor * 
        drainage_factor * 
        100
    )
    
    # Normalize to 0-100
    risk_score = min(100, max(0, raw_risk * 2))
    
    # Expected PCI loss (based on risk)
    # Base loss of 3-15 points depending on risk
    base_loss = 3 + (risk_score / 100) * 12
    expected_pci_loss = round(base_loss * pavement_vulnerability, 1)
    
    return risk_score, expected_pci_loss


def get_risk_level(risk_score: float, expected_pci_loss: float) -> WinterRiskLevel:
    """Determine risk level from score and expected loss"""
    if expected_pci_loss > 10 or risk_score > 75:
        return WinterRiskLevel.SEVERE
    elif expected_pci_loss > 7 or risk_score > 55:
        return WinterRiskLevel.HIGH
    elif expected_pci_loss > 4 or risk_score > 35:
        return WinterRiskLevel.MODERATE
    else:
        return WinterRiskLevel.LOW


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


def get_recommendation(
    risk_level: WinterRiskLevel,
    current_pci: float,
    post_winter_pci: float,
    crosses_threshold: bool
) -> tuple[str, str]:
    """Generate recommendation based on risk analysis"""
    if risk_level == WinterRiskLevel.SEVERE:
        if crosses_threshold:
            return (
                f"URGENT: Pre-winter crack sealing prevents crossing to {get_pci_condition(post_winter_pci)} condition",
                "Immediate crack sealing and waterproofing"
            )
        return (
            "High priority pre-winter treatment recommended",
            "Crack sealing and joint repair"
        )
    elif risk_level == WinterRiskLevel.HIGH:
        return (
            "Pre-winter maintenance strongly recommended",
            "Crack sealing in high-traffic areas"
        )
    elif risk_level == WinterRiskLevel.MODERATE:
        return (
            "Monitor condition, schedule spring assessment",
            "Targeted crack sealing if budget allows"
        )
    else:
        return (
            "Low winter risk - standard monitoring",
            "No immediate action required"
        )


class WinterResilienceService:
    """Service for winter damage prediction and intervention planning"""
    
    def __init__(self):
        self.road_service = RoadDegradationService()
    
    def analyze_winter_vulnerability(
        self,
        province: str,
        highway: str = None,
        limit: int = 100
    ) -> List[WinterVulnerability]:
        """
        Analyze winter vulnerability for road sections.
        
        Args:
            province: Province name
            highway: Optional specific highway
            limit: Max sections to analyze
            
        Returns:
            List of WinterVulnerability assessments
        """
        # Get road conditions from RoadDegradationService (handles MCP + fallback)
        result = self.road_service.get_road_conditions(
            province=province,
            highway=highway,
            limit=limit
        )
        
        if not result or "roads" not in result:
            return []
        
        roads = result["roads"]
        
        # Get climate data for province
        freeze_thaw = FREEZE_THAW_CYCLES.get(province, 45)
        climate_zone = CLIMATE_ZONES.get(province, province)
        
        vulnerabilities = []
        
        for road in roads:
            # Extract road data (handle None values)
            current_pci = road.get("pci") or 70
            pavement_type = road.get("pavement_type") or "AC"
            aadt = road.get("aadt")  # Keep None - function handles it
            dmi = road.get("dmi")    # Keep None - function handles it
            iri = road.get("iri")    # Keep None - function handles it
            
            # Calculate vulnerability factors
            pci_vuln = get_pci_vulnerability_factor(current_pci)
            pavement_vuln = PAVEMENT_VULNERABILITY.get(pavement_type, 1.0)
            traffic_factor = get_traffic_load_factor(aadt)
            drainage_factor = get_drainage_factor(dmi, iri)
            
            # Calculate risk
            risk_score, expected_loss = calculate_winter_damage_risk(
                current_pci, freeze_thaw, pavement_vuln, traffic_factor, drainage_factor
            )
            
            risk_level = get_risk_level(risk_score, expected_loss)
            
            # Calculate post-winter condition
            post_winter_pci = max(0, current_pci - expected_loss)
            current_condition = get_pci_condition(current_pci)
            post_winter_condition = get_pci_condition(post_winter_pci)
            
            # Check if crosses threshold
            crosses_threshold = current_condition != post_winter_condition
            threshold_crossed = f"{current_condition}→{post_winter_condition}" if crosses_threshold else ""
            
            # Get recommendation
            recommendation, action = get_recommendation(
                risk_level, current_pci, post_winter_pci, crosses_threshold
            )
            
            # Calculate costs (per km estimates)
            km_length = (road.get("km_end", 10) or 10) - (road.get("km_start", 0) or 0)
            km_length = max(1, abs(km_length))
            
            # Cost estimates per km
            if risk_level == WinterRiskLevel.SEVERE:
                pre_winter_cost = 45000 * km_length  # $45K/km for crack sealing
                spring_repair_cost = 320000 * km_length  # $320K/km for major repair
            elif risk_level == WinterRiskLevel.HIGH:
                pre_winter_cost = 35000 * km_length
                spring_repair_cost = 180000 * km_length
            elif risk_level == WinterRiskLevel.MODERATE:
                pre_winter_cost = 20000 * km_length
                spring_repair_cost = 80000 * km_length
            else:
                pre_winter_cost = 10000 * km_length
                spring_repair_cost = 30000 * km_length
            
            cost_savings = spring_repair_cost - pre_winter_cost
            roi = cost_savings / pre_winter_cost if pre_winter_cost > 0 else 0
            
            vuln = WinterVulnerability(
                highway=road.get("highway", "Unknown"),
                direction=road.get("direction", ""),
                section_from=road.get("section_from", ""),
                section_to=road.get("section_to", ""),
                km_start=road.get("km_start", 0) or 0,
                km_end=road.get("km_end", 0) or 0,
                current_pci=current_pci,
                current_condition=current_condition,
                pavement_type=pavement_type,
                climate_zone=climate_zone,
                freeze_thaw_cycles=freeze_thaw,
                pci_vulnerability_factor=round(pci_vuln, 2),
                pavement_vulnerability_factor=round(pavement_vuln, 2),
                traffic_load_factor=round(traffic_factor, 2),
                drainage_factor=round(drainage_factor, 2),
                winter_damage_risk_score=round(risk_score, 1),
                risk_level=risk_level.value,
                expected_pci_loss=expected_loss,
                post_winter_pci=round(post_winter_pci, 1),
                post_winter_condition=post_winter_condition,
                crosses_threshold=crosses_threshold,
                threshold_crossed=threshold_crossed,
                recommendation=recommendation,
                recommended_action=action,
                pre_winter_cost=pre_winter_cost,
                spring_repair_cost=spring_repair_cost,
                cost_savings=cost_savings,
                roi=round(roi, 1)
            )
            
            vulnerabilities.append(vuln)
        
        # Sort by risk score descending
        vulnerabilities.sort(key=lambda v: v.winter_damage_risk_score, reverse=True)
        
        return vulnerabilities
    
    def get_winter_forecast_summary(
        self,
        province: str,
        highway: str = None
    ) -> Optional[WinterForecastSummary]:
        """Get summary of winter forecast for a highway or province"""
        vulnerabilities = self.analyze_winter_vulnerability(province, highway, limit=500)
        
        if not vulnerabilities:
            return None
        
        severe_count = sum(1 for v in vulnerabilities if v.risk_level == "severe")
        high_count = sum(1 for v in vulnerabilities if v.risk_level == "high")
        moderate_count = sum(1 for v in vulnerabilities if v.risk_level == "moderate")
        low_count = sum(1 for v in vulnerabilities if v.risk_level == "low")
        
        # Calculate total km at risk (severe + high)
        at_risk = [v for v in vulnerabilities if v.risk_level in ["severe", "high"]]
        total_km_at_risk = sum(abs(v.km_end - v.km_start) for v in at_risk)
        
        avg_pci_loss = sum(v.expected_pci_loss for v in vulnerabilities) / len(vulnerabilities)
        crossing_count = sum(1 for v in vulnerabilities if v.crosses_threshold)
        
        total_pre_winter = sum(v.pre_winter_cost for v in at_risk)
        total_spring_avoided = sum(v.spring_repair_cost for v in at_risk)
        total_savings = sum(v.cost_savings for v in at_risk)
        overall_roi = total_savings / total_pre_winter if total_pre_winter > 0 else 0
        
        return WinterForecastSummary(
            province=province,
            highway=highway or "All Highways",
            total_sections=len(vulnerabilities),
            severe_risk_count=severe_count,
            high_risk_count=high_count,
            moderate_risk_count=moderate_count,
            low_risk_count=low_count,
            total_km_at_risk=round(total_km_at_risk, 1),
            average_expected_pci_loss=round(avg_pci_loss, 1),
            sections_crossing_threshold=crossing_count,
            total_pre_winter_investment=total_pre_winter,
            total_spring_repair_avoided=total_spring_avoided,
            total_potential_savings=total_savings,
            overall_roi=round(overall_roi, 1)
        )
    
    def calculate_pre_winter_intervention(
        self,
        province: str,
        highway: str,
        section_from: str = None
    ) -> List[PreWinterIntervention]:
        """
        Calculate ROI of pre-winter maintenance for road sections.
        
        Returns cost comparison:
        - Option A: Pre-winter crack sealing
        - Option B: Do nothing, wait for spring repair
        """
        vulnerabilities = self.analyze_winter_vulnerability(province, highway, limit=100)
        
        if not vulnerabilities:
            return []
        
        interventions = []
        
        for vuln in vulnerabilities:
            # Skip if looking for specific section
            if section_from and vuln.section_from != section_from:
                continue
            
            # Determine pre-winter action based on risk
            if vuln.risk_level == "severe":
                pre_winter_action = "Comprehensive crack sealing + waterproofing membrane"
                pci_loss_with_action = vuln.expected_pci_loss * 0.35  # Reduces loss by 65%
                traffic_disruption = 6
            elif vuln.risk_level == "high":
                pre_winter_action = "Crack sealing and joint repair"
                pci_loss_with_action = vuln.expected_pci_loss * 0.5  # Reduces loss by 50%
                traffic_disruption = 4
            elif vuln.risk_level == "moderate":
                pre_winter_action = "Targeted crack sealing"
                pci_loss_with_action = vuln.expected_pci_loss * 0.65  # Reduces loss by 35%
                traffic_disruption = 3
            else:
                pre_winter_action = "Routine maintenance"
                pci_loss_with_action = vuln.expected_pci_loss * 0.8
                traffic_disruption = 2
            
            spring_pci_with_action = vuln.current_pci - pci_loss_with_action
            spring_pci_without_action = vuln.post_winter_pci
            
            roi_multiplier = vuln.roi
            
            if roi_multiplier >= 5:
                recommendation = f"STRONGLY RECOMMENDED: {roi_multiplier:.1f}× return on investment"
            elif roi_multiplier >= 3:
                recommendation = f"Recommended: {roi_multiplier:.1f}× return on investment"
            elif roi_multiplier >= 1.5:
                recommendation = f"Consider: {roi_multiplier:.1f}× return on investment"
            else:
                recommendation = "Monitor only - low ROI"
            
            intervention = PreWinterIntervention(
                highway=vuln.highway,
                section=f"{vuln.section_from} to {vuln.section_to}",
                current_pci=vuln.current_pci,
                pre_winter_action=pre_winter_action,
                pre_winter_cost=vuln.pre_winter_cost,
                pci_loss_with_action=round(pci_loss_with_action, 1),
                spring_pci_with_action=round(spring_pci_with_action, 1),
                pci_loss_without_action=vuln.expected_pci_loss,
                spring_pci_without_action=round(spring_pci_without_action, 1),
                emergency_repair_cost=vuln.spring_repair_cost,
                traffic_disruption_weeks=traffic_disruption,
                cost_savings=vuln.cost_savings,
                roi_multiplier=roi_multiplier,
                recommendation=recommendation
            )
            
            interventions.append(intervention)
        
        return interventions


# Singleton instance
_winter_service: Optional[WinterResilienceService] = None


def get_winter_service() -> WinterResilienceService:
    """Get or create winter resilience service singleton"""
    global _winter_service
    if _winter_service is None:
        _winter_service = WinterResilienceService()
    return _winter_service
