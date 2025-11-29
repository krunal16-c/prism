from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import os
from dotenv import load_dotenv

import models, schemas, crud, database, risk_engine, optimizer, claude_service

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
    # 1. Interpret query with Claude
    interpretation = claude_service.interpret_query(request.query)
    
    # 2. Execute query (Mock implementation for now, real one would build dynamic SQL)
    # For MVP, we'll just return the interpretation and some mock results or filtered assets if simple
    
    filters = interpretation.get("filters", {})
    
    # Basic filtering logic
    query = db.query(models.Asset)
    if "province" in filters:
        query = query.filter(models.Asset.province == filters["province"])
    if "type" in filters:
        query = query.filter(models.Asset.type == filters["type"])
        
    results = query.limit(interpretation.get("limit", 20)).all()
    
    return {
        "query": request.query,
        "interpretation": interpretation.get("interpretation"),
        "filters": filters,
        "results": results,
        "result_count": len(results)
    }

@app.post("/api/optimize")
def optimize(request: schemas.OptimizationRequest, db: Session = Depends(get_db)):
    assets = crud.get_assets(db, limit=1000) # Get all assets
    result = optimizer.optimize_budget(assets, request.budget, request.priorities)
    return result

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
