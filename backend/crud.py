from sqlalchemy.orm import Session
import models, schemas
from risk_engine import calculate_risk_score
import datetime

def get_asset(db: Session, asset_id: int):
    return db.query(models.Asset).filter(models.Asset.id == asset_id).first()

def get_assets(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Asset).offset(skip).limit(limit).all()

def create_asset(db: Session, asset: schemas.AssetCreate):
    db_asset = models.Asset(**asset.dict())
    db.add(db_asset)
    db.commit()
    db.refresh(db_asset)
    return db_asset

def create_risk_score(db: Session, asset_id: int):
    asset = get_asset(db, asset_id)
    if not asset:
        return None
    
    risk_data = calculate_risk_score(asset)
    db_risk = models.RiskScore(asset_id=asset_id, **risk_data)
    
    db.add(db_risk)
    db.commit()
    db.refresh(db_risk)
    return db_risk
