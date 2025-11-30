from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
from dotenv import load_dotenv

import models, schemas, crud, database, risk_engine, optimizer, claude_service
import government_data_service

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
