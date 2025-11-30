from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from dotenv import load_dotenv

import models, schemas, crud, database, risk_engine, optimizer, claude_service
import government_data_service
import road_degradation_service

load_dotenv()

# Create tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="PRISM API", description="Predictive Resource Intelligence for Strategic Management")

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "PRISM API"}

@app.get("/api/assets", response_model=List[schemas.Asset])
def read_assets(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    assets = crud.get_assets(db, skip=skip, limit=limit)
    return assets

@app.get("/api/assets/{asset_id}", response_model=schemas.Asset)
def read_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = crud.get_asset(db, asset_id=asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset

@app.post("/api/risk/calculate", response_model=schemas.RiskScore)
def calculate_risk(request: schemas.RiskCalculationRequest, db: Session = Depends(get_db)):
    risk_score = crud.create_risk_score(db, request.asset_id)
    if risk_score is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return risk_score

@app.post("/api/query/nl")
def nl_query(request: schemas.NLQueryRequest, db: Session = Depends(get_db)):
    """
    Natural language query endpoint.
    Supports both asset queries (internal DB) and bridge queries (Government data).
    """
    # 1. Interpret query with Claude/Gemini
    interpretation = claude_service.interpret_query(request.query)
    
    data_source = interpretation.get("data_source", "assets")
    filters = interpretation.get("filters", {})
    limit = interpretation.get("limit", 20)
    
    # 2. Execute query based on data source
    if data_source == "bridges":
        # Query government bridge data
        province = filters.get("province", "Ontario")
        condition_filter = filters.get("condition")
        
        bridges = government_data_service.get_bridge_locations(province, limit=200)
        
        if bridges and condition_filter:
            # Filter by condition
            bridges = [b for b in bridges if b.get("condition", "").lower() == condition_filter.lower()]
        
        # Limit results
        bridges = bridges[:limit] if bridges else []
        
        return {
            "query": request.query,
            "interpretation": interpretation.get("interpretation"),
            "data_source": "bridges",
            "filters": filters,
            "results": bridges,
            "result_count": len(bridges),
            "province": province
        }
    else:
        # Query internal assets database
        query = db.query(models.Asset)
        if "province" in filters:
            query = query.filter(models.Asset.province == filters["province"])
        if "type" in filters:
            query = query.filter(models.Asset.type == filters["type"])
            
        results = query.limit(limit).all()
        
        return {
            "query": request.query,
            "interpretation": interpretation.get("interpretation"),
            "data_source": "assets",
            "filters": filters,
            "results": results,
            "result_count": len(results)
        }

@app.post("/api/optimize")
def optimize(request: schemas.OptimizationRequest, db: Session = Depends(get_db)):
    assets = crud.get_assets(db, limit=1000) # Get all assets
    result = optimizer.optimize_budget(assets, request.budget, request.priorities)
    return result


# ============================================
# Government Data Dashboard API Endpoints
# ============================================

@app.get("/api/dashboard/regions")
def get_regions():
    """Get list of all supported regions/provinces"""
    regions = government_data_service.get_all_regions()
    return {
        "regions": regions,
        "default_region": "Ontario",
        "count": len(regions)
    }


@app.get("/api/dashboard/summary/{region}")
def get_dashboard_summary(
    region: str,
    force_refresh: bool = Query(default=False, description="Force refresh from MCP servers")
):
    """
    Get comprehensive dashboard summary for a specific region.
    Uses cached data (24-hour TTL) unless force_refresh is True.
    """
    summary = government_data_service.get_dashboard_summary(region, force_refresh=force_refresh)
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {region}. Please select another region."
        )
    return summary


@app.get("/api/dashboard/bridges/{region}")
def get_bridge_locations(
    region: str,
    limit: int = Query(default=100, le=500, ge=10),
    force_refresh: bool = Query(default=False, description="Force refresh from MCP servers")
):
    """
    Get individual bridge locations for map display.
    Uses cached data (24-hour TTL) unless force_refresh is True.
    """
    bridges = government_data_service.get_bridge_locations(region, limit, force_refresh=force_refresh)
    if bridges is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {region}. Please select another region."
        )
    return {
        "region": region,
        "bridges": bridges,
        "count": len(bridges),
        "data_source": "Statistics Canada"
    }


@app.get("/api/dashboard/national")
def get_national_summary():
    """Get aggregated national statistics across all provinces"""
    return government_data_service.get_national_summary()


@app.get("/api/dashboard/conditions/{region}")
def get_bridge_conditions(
    region: str,
    force_refresh: bool = Query(default=False, description="Force refresh from MCP servers")
):
    """Get detailed bridge condition breakdown for a region"""
    conditions = government_data_service.get_bridge_conditions(region, force_refresh=force_refresh)
    if not conditions:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {region}. Please select another region."
        )
    return conditions


@app.get("/api/dashboard/costs/{region}")
def get_infrastructure_costs(
    region: str,
    force_refresh: bool = Query(default=False, description="Force refresh from MCP servers")
):
    """Get infrastructure cost and investment data for a region"""
    costs = government_data_service.get_infrastructure_costs(region, force_refresh=force_refresh)
    if not costs:
        raise HTTPException(
            status_code=404,
            detail=f"No data available for {region}. Please select another region."
        )
    return costs


@app.get("/api/mcp/status")
def get_mcp_status():
    """Check status of MCP server connections"""
    return government_data_service.get_mcp_server_status()


# ============================================
# Highway Degradation Forecaster API (Feature)
# ============================================

@app.get("/api/roads/conditions")
def get_road_conditions(
    province: Optional[str] = Query(default=None, description="Filter by province"),
    highway: Optional[str] = Query(default=None, description="Filter by highway name"),
    condition: Optional[str] = Query(default=None, description="Filter by condition (good/fair/poor/critical)"),
    limit: int = Query(default=100, le=5000, ge=10)
):
    """
    Get road condition data from MCP or fallback.
    Returns PCI, DMI, IRI, pavement type, and coordinates.
    """
    service = road_degradation_service.get_road_degradation_service()
    result = service.get_road_conditions(
        province=province,
        highway=highway,
        condition=condition,
        limit=limit
    )
    return {
        "roads": result.get("roads", []),
        "count": len(result.get("roads", [])),
        "source": result.get("source", "unknown"),
        "filters": {
            "province": province,
            "highway": highway,
            "condition": condition
        }
    }


@app.get("/api/roads/forecast/{highway}")
def get_road_forecast(
    highway: str,
    province: str = Query(..., description="Province for the highway"),
    years: int = Query(default=10, le=20, ge=1, description="Forecast horizon in years")
):
    """
    Get degradation forecast for a specific highway.
    Returns PCI predictions, optimal intervention timing, and cost analysis.
    """
    service = road_degradation_service.get_road_degradation_service()
    forecasts = service.forecast_degradation(highway, province, years)
    
    if not forecasts:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for highway {highway} in {province}"
        )
    
    # Convert dataclass objects to dicts
    forecast_dicts = []
    for f in forecasts:
        forecast_dicts.append({
            "highway": f.highway,
            "section": f.section,
            "current_pci": f.current_pci,
            "predicted_pci": f.predicted_pci,
            "years_to_critical": f.years_to_critical,
            "optimal_intervention_year": f.optimal_intervention_year,
            "optimal_intervention_pci": f.optimal_intervention_pci,
            "estimated_cost_now": f.estimated_cost_now,
            "estimated_cost_optimal": f.estimated_cost_optimal,
            "estimated_cost_delayed": f.estimated_cost_delayed,
            "cost_savings_optimal": f.cost_savings_optimal,
            "degradation_rate": f.degradation_rate,
        })
    
    # Summary statistics
    avg_pci = sum(f.current_pci for f in forecasts) / len(forecasts) if forecasts else 0
    critical_sections = len([f for f in forecasts if f.current_pci < 40])
    poor_sections = len([f for f in forecasts if 40 <= f.current_pci < 60])
    total_cost_now = sum(f.estimated_cost_now for f in forecasts)
    total_cost_optimal = sum(f.estimated_cost_optimal for f in forecasts)
    total_savings = sum(f.cost_savings_optimal for f in forecasts)
    
    return {
        "highway": highway,
        "province": province,
        "forecast_years": years,
        "sections": forecast_dicts,
        "section_count": len(forecast_dicts),
        "summary": {
            "average_pci": round(avg_pci, 1),
            "critical_sections": critical_sections,
            "poor_sections": poor_sections,
            "total_cost_if_repaired_now": round(total_cost_now, 0),
            "total_cost_at_optimal_time": round(total_cost_optimal, 0),
            "potential_savings": round(total_savings, 0)
        }
    }


@app.get("/api/roads/economic-impact")
def get_economic_impact(
    province: Optional[str] = Query(default=None, description="Filter by province"),
    highway: Optional[str] = Query(default=None, description="Filter by highway"),
    condition: Optional[str] = Query(default=None, description="Filter by condition")
):
    """
    Calculate economic impact of road conditions.
    Returns vehicle damage, fuel waste, freight delays, and ROI analysis.
    """
    service = road_degradation_service.get_road_degradation_service()
    impacts = service.get_economic_impact(
        province=province,
        highway=highway,
        condition=condition
    )
    
    # Convert dataclass objects to dicts
    impact_dicts = []
    for i in impacts:
        impact_dicts.append({
            "highway": i.highway,
            "section": i.section,
            "pci": i.pci,
            "condition": i.condition,
            "daily_traffic": i.daily_traffic,
            "annual_vehicle_damage_cost": i.annual_vehicle_damage_cost,
            "annual_fuel_waste_cost": i.annual_fuel_waste_cost,
            "annual_freight_delay_cost": i.annual_freight_delay_cost,
            "total_annual_cost": i.total_annual_cost,
            "roi_if_repaired": i.roi_if_repaired,
        })
    
    # Summary
    total_damage = sum(i.annual_vehicle_damage_cost for i in impacts)
    total_fuel = sum(i.annual_fuel_waste_cost for i in impacts)
    total_freight = sum(i.annual_freight_delay_cost for i in impacts)
    total_cost = sum(i.total_annual_cost for i in impacts)
    avg_roi = sum(i.roi_if_repaired for i in impacts) / len(impacts) if impacts else 0
    
    return {
        "impacts": impact_dicts,
        "count": len(impact_dicts),
        "filters": {
            "province": province,
            "highway": highway,
            "condition": condition
        },
        "summary": {
            "total_annual_vehicle_damage": round(total_damage, 0),
            "total_annual_fuel_waste": round(total_fuel, 0),
            "total_annual_freight_delay": round(total_freight, 0),
            "total_annual_economic_cost": round(total_cost, 0),
            "average_roi_if_repaired": round(avg_roi, 2)
        }
    }


@app.get("/api/roads/heatmap")
def get_road_heatmap(
    province: Optional[str] = Query(default=None, description="Filter by province"),
    min_pci: Optional[float] = Query(default=None, description="Minimum PCI filter"),
    max_pci: Optional[float] = Query(default=None, description="Maximum PCI filter")
):
    """
    Get road network heatmap data for visualization.
    Returns segments with coordinates, colors, and weights for map rendering.
    """
    service = road_degradation_service.get_road_degradation_service()
    heatmap_data = service.get_network_heatmap_data(
        province=province,
        min_pci=min_pci,
        max_pci=max_pci
    )
    return heatmap_data


@app.get("/api/roads/highways/{province}")
def get_highways_for_province(province: str):
    """
    Get list of available highways for a province.
    Used for dropdown selection in the forecast UI.
    """
    from models import CachedRoadCondition
    from sqlalchemy import distinct
    
    db = next(get_db())
    try:
        # Query unique highways directly from database
        highways = db.query(distinct(CachedRoadCondition.highway)).filter(
            CachedRoadCondition.province == province
        ).all()
        highways = sorted([h[0] for h in highways if h[0]])
        
        return {
            "province": province,
            "highways": highways,
            "count": len(highways)
        }
    finally:
        db.close()


# ============================================
# Winter Resilience Endpoints (Feature 11)
# ============================================

@app.get("/api/roads/winter/vulnerability")
def get_winter_vulnerability(
    province: str,
    highway: Optional[str] = None,
    limit: int = 100
):
    """
    Get winter vulnerability analysis for road sections.
    
    Returns freeze-thaw damage predictions including:
    - Expected PCI loss over winter
    - Risk level (severe/high/moderate/low)
    - Pre-winter intervention recommendations
    - Cost savings from preventive maintenance
    """
    from winter_resilience_service import get_winter_service
    service = get_winter_service()
    
    vulnerabilities = service.analyze_winter_vulnerability(
        province=province,
        highway=highway,
        limit=limit
    )
    
    return {
        "province": province,
        "highway": highway or "All Highways",
        "winter_season": "2025-2026",
        "vulnerabilities": [
            {
                "highway": v.highway,
                "direction": v.direction,
                "section_from": v.section_from,
                "section_to": v.section_to,
                "km_start": v.km_start,
                "km_end": v.km_end,
                "current_pci": v.current_pci,
                "current_condition": v.current_condition,
                "pavement_type": v.pavement_type,
                "climate_zone": v.climate_zone,
                "freeze_thaw_cycles": v.freeze_thaw_cycles,
                "pci_vulnerability_factor": v.pci_vulnerability_factor,
                "pavement_vulnerability_factor": v.pavement_vulnerability_factor,
                "traffic_load_factor": v.traffic_load_factor,
                "drainage_factor": v.drainage_factor,
                "winter_damage_risk_score": v.winter_damage_risk_score,
                "risk_level": v.risk_level,
                "expected_pci_loss": v.expected_pci_loss,
                "post_winter_pci": v.post_winter_pci,
                "post_winter_condition": v.post_winter_condition,
                "crosses_threshold": v.crosses_threshold,
                "threshold_crossed": v.threshold_crossed,
                "recommendation": v.recommendation,
                "recommended_action": v.recommended_action,
                "pre_winter_cost": v.pre_winter_cost,
                "spring_repair_cost": v.spring_repair_cost,
                "cost_savings": v.cost_savings,
                "roi": v.roi
            }
            for v in vulnerabilities
        ],
        "count": len(vulnerabilities)
    }


@app.get("/api/roads/winter/forecast-summary")
def get_winter_forecast_summary(
    province: str,
    highway: Optional[str] = None
):
    """
    Get summary of winter damage forecast for a highway or province.
    
    Returns:
    - Risk distribution (severe/high/moderate/low counts)
    - Total km at risk
    - Average expected PCI loss
    - Total pre-winter investment needed
    - Potential savings from preventive maintenance
    """
    from winter_resilience_service import get_winter_service
    service = get_winter_service()
    
    summary = service.get_winter_forecast_summary(province, highway)
    
    if not summary:
        return {
            "province": province,
            "highway": highway or "All Highways",
            "error": "No data available"
        }
    
    return {
        "province": summary.province,
        "highway": summary.highway,
        "winter_season": "2025-2026",
        "total_sections": summary.total_sections,
        "risk_distribution": {
            "severe": summary.severe_risk_count,
            "high": summary.high_risk_count,
            "moderate": summary.moderate_risk_count,
            "low": summary.low_risk_count
        },
        "total_km_at_risk": summary.total_km_at_risk,
        "average_expected_pci_loss": summary.average_expected_pci_loss,
        "sections_crossing_threshold": summary.sections_crossing_threshold,
        "financials": {
            "total_pre_winter_investment": summary.total_pre_winter_investment,
            "total_spring_repair_avoided": summary.total_spring_repair_avoided,
            "total_potential_savings": summary.total_potential_savings,
            "overall_roi": summary.overall_roi
        }
    }


@app.get("/api/roads/winter/interventions")
def get_pre_winter_interventions(
    province: str,
    highway: str,
    section_from: Optional[str] = None
):
    """
    Get pre-winter intervention analysis comparing:
    - Option A: Pre-winter crack sealing (proactive)
    - Option B: Do nothing, spring emergency repair (reactive)
    
    Returns ROI analysis for each section.
    """
    from winter_resilience_service import get_winter_service
    service = get_winter_service()
    
    interventions = service.calculate_pre_winter_intervention(
        province=province,
        highway=highway,
        section_from=section_from
    )
    
    return {
        "province": province,
        "highway": highway,
        "interventions": [
            {
                "highway": i.highway,
                "section": i.section,
                "current_pci": i.current_pci,
                "option_a": {
                    "name": "Pre-Winter Action",
                    "action": i.pre_winter_action,
                    "cost": i.pre_winter_cost,
                    "pci_loss": i.pci_loss_with_action,
                    "spring_pci": i.spring_pci_with_action
                },
                "option_b": {
                    "name": "Do Nothing",
                    "pci_loss": i.pci_loss_without_action,
                    "spring_pci": i.spring_pci_without_action,
                    "emergency_repair_cost": i.emergency_repair_cost,
                    "traffic_disruption_weeks": i.traffic_disruption_weeks
                },
                "analysis": {
                    "cost_savings": i.cost_savings,
                    "roi_multiplier": i.roi_multiplier,
                    "recommendation": i.recommendation
                }
            }
            for i in interventions
        ],
        "count": len(interventions)
    }


# ============================================
# Corridor Optimization Endpoints (Feature 12)
# ============================================

@app.get("/api/roads/corridor/bundles")
def get_corridor_bundles(
    province: str,
    highway: Optional[str] = None,
    min_length_km: float = 20
):
    """
    Find bundle opportunities for adjacent road sections.
    
    Bundling benefits:
    - Contractor mobilization costs shared (15-20% savings)
    - Traffic management once vs multiple times
    - Continuous smooth driving experience
    - May qualify for federal infrastructure funding (>$20M)
    """
    from corridor_optimization_service import get_corridor_service
    service = get_corridor_service()
    
    bundles = service.find_bundle_opportunities(
        province=province,
        highway=highway,
        min_bundle_length_km=min_length_km
    )
    
    return {
        "province": province,
        "highway": highway or "All Highways",
        "bundles": [
            {
                "bundle_id": b.bundle_id,
                "highway": b.highway,
                "direction": b.direction,
                "geometry": {
                    "start_km": b.start_km,
                    "end_km": b.end_km,
                    "total_length_km": b.total_length_km,
                    "continuous_smooth_km": b.continuous_smooth_km
                },
                "condition": {
                    "average_pci": b.average_pci,
                    "min_pci": b.min_pci,
                    "max_pci": b.max_pci,
                    "sections_count": b.sections_needing_repair
                },
                "cost_analysis": {
                    "individual_approach_cost": b.individual_cost,
                    "bundled_approach_cost": b.bundled_cost,
                    "savings": b.savings,
                    "savings_percent": b.savings_percent,
                    "mobilization_savings": b.mobilization_savings
                },
                "benefits": {
                    "traffic_disruptions_avoided": b.traffic_disruptions_avoided,
                    "qualifies_for_federal_funding": b.qualifies_for_federal_funding,
                    "federal_funding_threshold": b.federal_funding_threshold
                },
                "sections": [
                    {
                        "section_from": s.section_from,
                        "section_to": s.section_to,
                        "km_start": s.km_start,
                        "km_end": s.km_end,
                        "pci": s.pci,
                        "condition": s.condition
                    }
                    for s in b.sections
                ]
            }
            for b in bundles
        ],
        "count": len(bundles)
    }


@app.get("/api/roads/corridor/directional-analysis")
def get_directional_analysis(
    province: str,
    highway: str
):
    """
    Compare road conditions between opposite directions on the same highway.
    
    Use cases:
    - Identify heavier truck traffic in one direction
    - Find single-direction repair opportunities
    - Understand asymmetric degradation patterns
    """
    from corridor_optimization_service import get_corridor_service
    service = get_corridor_service()
    
    analyses = service.analyze_directional_conditions(province, highway)
    
    if not analyses:
        return {
            "province": province,
            "highway": highway,
            "error": "Insufficient directional data"
        }
    
    return {
        "province": province,
        "highway": highway,
        "analyses": [
            {
                "highway": a.highway,
                "km_range": a.km_range,
                "direction_1": {
                    "name": a.direction_1,
                    "sections": a.direction_1_sections,
                    "avg_pci": a.direction_1_avg_pci,
                    "avg_iri": a.direction_1_avg_iri,
                    "avg_dmi": a.direction_1_avg_dmi,
                    "truck_percent": a.direction_1_truck_percent
                },
                "direction_2": {
                    "name": a.direction_2,
                    "sections": a.direction_2_sections,
                    "avg_pci": a.direction_2_avg_pci,
                    "avg_iri": a.direction_2_avg_iri,
                    "avg_dmi": a.direction_2_avg_dmi,
                    "truck_percent": a.direction_2_truck_percent
                },
                "comparison": {
                    "pci_difference": a.pci_difference,
                    "worse_direction": a.worse_direction,
                    "degradation_reason": a.degradation_reason
                },
                "recommendation": {
                    "action": a.recommendation,
                    "single_direction_cost": a.single_direction_repair_cost,
                    "both_directions_cost": a.both_directions_repair_cost,
                    "potential_savings": a.potential_savings
                }
            }
            for a in analyses
        ],
        "count": len(analyses)
    }


@app.get("/api/roads/corridor/summary")
def get_corridor_summary(
    province: str,
    highway: Optional[str] = None
):
    """
    Get summary of corridor optimization opportunities.
    
    Returns:
    - Total bundles and bundled length
    - Total savings from bundling
    - Directional disparity count
    - Top bundle opportunity
    """
    from corridor_optimization_service import get_corridor_service
    service = get_corridor_service()
    
    summary = service.get_corridor_summary(province, highway)
    
    if not summary:
        return {
            "province": province,
            "highway": highway or "All Highways",
            "error": "No data available"
        }
    
    return {
        "province": summary.province,
        "highway": summary.highway,
        "bundles": {
            "total_bundles": summary.total_bundles,
            "total_sections_bundled": summary.total_sections_bundled,
            "total_bundled_length_km": summary.total_bundled_length_km
        },
        "savings": {
            "total_individual_cost": summary.total_individual_cost,
            "total_bundled_cost": summary.total_bundled_cost,
            "total_savings": summary.total_savings,
            "average_savings_percent": summary.average_savings_percent
        },
        "directional": {
            "directions_with_disparity": summary.directions_with_disparity,
            "single_direction_opportunities": summary.single_direction_opportunities
        },
        "top_opportunity": {
            "bundle_id": summary.top_bundle_id,
            "savings": summary.top_bundle_savings
        }
    }


# ============================================
# Cache Management / Admin Endpoints
# ============================================

@app.get("/api/cache/status")
def get_cache_status(region: Optional[str] = None):
    """
    Get cache status for a specific region or all regions.
    Shows cache age, validity, and sync status.
    """
    return government_data_service.get_cache_status_for_region(region)


@app.post("/api/cache/refresh/{region}")
def refresh_region_cache(region: str):
    """
    Force refresh cache for a specific region from MCP servers.
    Use region='all' to refresh all regions.
    """
    result = government_data_service.sync_region_from_mcp(region)
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh cache: {result.get('error', 'Unknown error')}"
        )
    return result


@app.delete("/api/cache/{region}")
def invalidate_cache(region: str):
    """
    Invalidate cache for a specific region.
    Use region='all' to invalidate all cached data.
    """
    from cache_service import invalidate_cache as do_invalidate
    count = do_invalidate(region if region != "all" else None)
    return {
        "success": True,
        "regions_invalidated": count,
        "message": f"Cache invalidated for {region if region != 'all' else 'all regions'}"
    }


# ============================================
# Seed Data Endpoint
# ============================================

# Seed data endpoint for demo
@app.post("/api/seed")
def seed_data(db: Session = Depends(get_db)):
    # Check if data exists
    if db.query(models.Asset).count() > 0:
        return {"message": "Data already seeded"}
        
    # Generate synthetic data (simplified for now)
    import random
    
    provinces = ["Nova Scotia", "New Brunswick", "Newfoundland and Labrador", "Prince Edward Island"]
    types = ["bridge", "road", "facility"]
    
    for i in range(150):
        prov = random.choice(provinces)
        atype = random.choice(types)
        
        # Lat/Lon ranges for Atlantic Canada
        lat = random.uniform(44.0, 48.0)
        lon = random.uniform(-66.0, -52.0)
        
        asset = schemas.AssetCreate(
            name=f"{prov} {atype.capitalize()} {i+1}",
            type=atype,
            latitude=lat,
            longitude=lon,
            province=prov,
            year_built=random.randint(1950, 2020),
            condition_index=random.uniform(10, 95),
            daily_usage=random.randint(100, 50000),
            criticality=random.choice(["low", "medium", "high", "critical"]),
            climate_zone=random.choice(["Coastal Atlantic", "Interior Atlantic"]),
            serves_essential_services=random.choice([True, False])
        )
        crud.create_asset(db, asset)
        
    return {"message": "Seeded 150 assets"}
