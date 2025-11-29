from pydantic import BaseModel
from typing import List, Optional

class RiskScoreBase(BaseModel):
    overall_score: float
    condition_score: float
    usage_score: float
    climate_score: float
    redundancy_score: float
    population_impact_score: float
    explanation: Optional[str] = None
    calculated_date: str

class RiskScore(RiskScoreBase):
    id: int
    asset_id: int

    class Config:
        orm_mode = True

class AssetBase(BaseModel):
    name: str
    type: str
    latitude: float
    longitude: float
    province: str
    municipality: Optional[str] = None
    year_built: Optional[int] = None
    last_inspection_date: Optional[str] = None
    condition_index: Optional[float] = None
    daily_usage: Optional[int] = None
    criticality: Optional[str] = None
    redundancy_available: bool = False
    climate_zone: Optional[str] = None
    serves_essential_services: bool = False

class AssetCreate(AssetBase):
    pass

class Asset(AssetBase):
    id: int
    risk_scores: List[RiskScore] = []

    class Config:
        orm_mode = True

class RiskCalculationRequest(BaseModel):
    asset_id: int

class NLQueryRequest(BaseModel):
    query: str

class OptimizationRequest(BaseModel):
    budget: float
    priorities: dict
