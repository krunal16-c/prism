from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime, timezone


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


# ============================================
# Infrastructure Data Cache Models
# ============================================

class CachedRegionData(Base):
    """
    Cached infrastructure summary data per region.
    Stores condition breakdowns, costs, and metadata.
    Refreshed on-demand when data is older than 24 hours.
    """
    __tablename__ = "cached_region_data"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String, unique=True, nullable=False, index=True)
    
    # Bridge condition data
    total_bridges = Column(Integer, default=0)
    good_count = Column(Integer, default=0)
    good_percentage = Column(Float, default=0.0)
    fair_count = Column(Integer, default=0)
    fair_percentage = Column(Float, default=0.0)
    poor_count = Column(Integer, default=0)
    poor_percentage = Column(Float, default=0.0)
    critical_count = Column(Integer, default=0)
    critical_percentage = Column(Float, default=0.0)
    unknown_count = Column(Integer, default=0)
    unknown_percentage = Column(Float, default=0.0)
    
    # Cost data
    replacement_value_billions = Column(Float, default=0.0)
    replacement_value_millions = Column(Float, default=0.0)
    priority_investment_millions = Column(Float, default=0.0)
    
    # Metadata
    data_source = Column(String, default="Statistics Canada")
    statcan_table_id = Column(String, nullable=True)
    reference_year = Column(String, nullable=True)
    
    # Cache management
    cached_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_mcp_sync = Column(DateTime, nullable=True)
    sync_status = Column(String, default="pending")  # pending, synced, failed
    sync_error = Column(Text, nullable=True)


class CachedBridgeLocation(Base):
    """
    Cached individual bridge locations for map display.
    Linked to a region for easy querying.
    """
    __tablename__ = "cached_bridge_locations"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String, nullable=False, index=True)
    bridge_id = Column(String, nullable=False)  # e.g., "ONT-0001"
    
    # Basic info
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    condition = Column(String, nullable=False)  # Good, Fair, Poor, Critical, Unknown
    condition_index = Column(String, nullable=True)  # Original numeric rating
    
    # Details
    year_built = Column(String, nullable=True)
    last_inspection = Column(String, nullable=True)
    highway = Column(String, nullable=True)
    structure_type = Column(String, nullable=True)
    category = Column(String, nullable=True)
    material = Column(String, nullable=True)
    owner = Column(String, nullable=True)
    status = Column(String, nullable=True)
    county = Column(String, nullable=True)
    source = Column(String, nullable=True)
    
    # Cache management
    cached_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class DataSyncLog(Base):
    """
    Log of all data synchronization attempts.
    Useful for debugging and monitoring.
    """
    __tablename__ = "data_sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    region = Column(String, nullable=False, index=True)
    sync_type = Column(String, nullable=False)  # conditions, costs, bridges, full
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="in_progress")  # in_progress, success, failed
    records_synced = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    mcp_response_time_ms = Column(Integer, nullable=True)
