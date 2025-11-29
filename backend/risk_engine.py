from models import Asset
import datetime

def calculate_risk_score(asset: Asset):
    # 1. Condition Score (25%)
    # Lower condition index = Higher risk. 
    # Also factor in age (older = higher risk).
    current_year = datetime.datetime.now().year
    age = current_year - (asset.year_built or 1980)
    
    # Normalize age: 0-100 (cap at 100 years)
    age_factor = min(age, 100)
    
    # Condition index is 0-100 (100 is good). Risk is inverse.
    condition_risk = (100 - (asset.condition_index or 50)) 
    
    # Weighted condition score: 70% condition index, 30% age
    condition_score = (condition_risk * 0.7) + (age_factor * 0.3)

    # 2. Usage Score (20%)
    # Higher usage = Higher risk/impact
    usage = asset.daily_usage or 0
    # Logarithmic scaling or simple tiered
    if usage > 20000:
        usage_score = 100
    elif usage > 10000:
        usage_score = 80
    elif usage > 5000:
        usage_score = 60
    elif usage > 1000:
        usage_score = 40
    else:
        usage_score = 20

    # 3. Climate Score (20%)
    # Based on zone and type
    climate_score = 50 # Default
    if asset.climate_zone == "Coastal Atlantic":
        climate_score += 20
    if asset.type == "bridge":
        climate_score += 10 # Bridges more exposed

    # 4. Redundancy Score (15%)
    # No redundancy = High risk (100)
    redundancy_score = 0 if asset.redundancy_available else 100

    # 5. Population Impact Score (20%)
    # Essential services = High impact
    pop_score = 50
    if asset.serves_essential_services:
        pop_score = 100
    elif asset.criticality == "high":
        pop_score = 80
    
    # Calculate Overall Score
    overall_score = (
        (condition_score * 0.25) +
        (usage_score * 0.20) +
        (climate_score * 0.20) +
        (redundancy_score * 0.15) +
        (pop_score * 0.20)
    )

    explanation = (
        f"Overall Risk: {overall_score:.1f}/100. "
        f"Driven by Condition ({condition_score:.1f}), Usage ({usage_score}), "
        f"Climate ({climate_score}), Redundancy ({redundancy_score}), "
        f"and Impact ({pop_score})."
    )

    return {
        "overall_score": min(max(overall_score, 0), 100),
        "condition_score": condition_score,
        "usage_score": usage_score,
        "climate_score": climate_score,
        "redundancy_score": redundancy_score,
        "population_impact_score": pop_score,
        "explanation": explanation,
        "calculated_date": datetime.datetime.now().isoformat()
    }
