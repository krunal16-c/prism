from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base

class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # bridge, road, facility
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    province = Column(String, nullable=False)
    municipality = Column(String, nullable=True)
    year_built = Column(Integer, nullable=True)
    last_inspection_date = Column(String, nullable=True)
    condition_index = Column(Float, nullable=True)  # 0-100
    daily_usage = Column(Integer, nullable=True)
    criticality = Column(String, nullable=True)  # low, medium, high, critical
    redundancy_available = Column(Boolean, default=False)
    climate_zone = Column(String, nullable=True)
    serves_essential_services = Column(Boolean, default=False)

    risk_scores = relationship("RiskScore", back_populates="asset")

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"))
    calculated_date = Column(String, nullable=False)
    overall_score = Column(Float, nullable=False)
    condition_score = Column(Float, nullable=False)
    usage_score = Column(Float, nullable=False)
    climate_score = Column(Float, nullable=False)
    redundancy_score = Column(Float, nullable=False)
    population_impact_score = Column(Float, nullable=False)
    explanation = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="risk_scores")
