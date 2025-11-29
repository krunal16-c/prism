from typing import List, Dict
from models import Asset

def optimize_budget(assets: List[Asset], budget: float, priorities: Dict[str, float]):
    # priorities: cost_efficiency, regional_equity, climate_resilience, population_impact
    
    scored_assets = []
    
    for asset in assets:
        # Calculate a composite score based on priorities
        # This is a simplified version. In a real app, we'd use the risk score components.
        # For now, let's assume we have risk scores or calculate them on the fly if needed.
        # We'll use the latest risk score if available, or a default.
        
        latest_score = asset.risk_scores[-1] if asset.risk_scores else None
        base_risk = latest_score.overall_score if latest_score else 50
        
        # Normalize priorities to 0-1
        p_cost = priorities.get("cost_efficiency", 50) / 100
        p_equity = priorities.get("regional_equity", 50) / 100
        p_climate = priorities.get("climate_resilience", 50) / 100
        p_pop = priorities.get("population_impact", 50) / 100
        
        # Calculate weighted score
        # Higher score = higher priority for funding
        weighted_score = (
            (base_risk * p_cost) + 
            ((100 if asset.climate_zone == "Coastal Atlantic" else 0) * p_climate) +
            ((100 if asset.serves_essential_services else 0) * p_pop)
        )
        
        # Estimated cost (randomized for MVP or based on type)
        estimated_cost = 1000000 # Default $1M
        if asset.type == "bridge":
            estimated_cost = 5000000
        elif asset.type == "road":
            estimated_cost = 2000000
            
        scored_assets.append({
            "asset": asset,
            "score": weighted_score,
            "cost": estimated_cost,
            "risk_reduction": base_risk * 0.2 # Simplified assumption
        })
        
    # Sort by score descending
    scored_assets.sort(key=lambda x: x["score"], reverse=True)
    
    funded_assets = []
    remaining_budget = budget
    total_risk_reduction = 0
    population_protected = 0
    regional_counts = {}
    
    for item in scored_assets:
        if item["cost"] <= remaining_budget:
            funded_assets.append({
                "asset_id": item["asset"].id,
                "asset_name": item["asset"].name,
                "cost": item["cost"],
                "score": item["score"]
            })
            remaining_budget -= item["cost"]
            total_risk_reduction += item["risk_reduction"]
            population_protected += (item["asset"].daily_usage or 0)
            
            prov = item["asset"].province
            regional_counts[prov] = regional_counts.get(prov, 0) + 1
            
    return {
        "assets_funded_count": len(funded_assets),
        "total_assets_considered": len(assets),
        "total_cost": budget - remaining_budget,
        "total_risk_reduction": round(total_risk_reduction, 2),
        "population_protected": population_protected,
        "regional_distribution": regional_counts,
        "allocations": funded_assets
    }
