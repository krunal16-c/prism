"""
Cache Service for Infrastructure Data
Handles on-demand caching of MCP data with 24-hour TTL.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_
import time

from models import CachedRegionData, CachedBridgeLocation, DataSyncLog
from database import SessionLocal

# Cache TTL in hours
CACHE_TTL_HOURS = 24


def get_db_session() -> Session:
    """Get a database session"""
    return SessionLocal()


def is_cache_valid(cached_at: Optional[datetime], ttl_hours: int = CACHE_TTL_HOURS) -> bool:
    """Check if cached data is still valid (within TTL)"""
    if cached_at is None:
        return False
    
    # Handle timezone-aware and naive datetimes
    now = datetime.now(timezone.utc)
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=timezone.utc)
    
    age = now - cached_at
    return age < timedelta(hours=ttl_hours)


def get_cached_region_data(region: str, db: Session = None) -> Optional[Dict]:
    """
    Get cached region data if valid.
    Returns None if cache is missing or expired.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        cached = db.query(CachedRegionData).filter(
            CachedRegionData.region == region
        ).first()
        
        if cached and is_cache_valid(cached.cached_at):
            return _cached_region_to_dict(cached)
        
        return None
    finally:
        if close_db:
            db.close()


def get_cached_bridges(region: str, limit: int = 100, db: Session = None) -> Optional[List[Dict]]:
    """
    Get cached bridge locations for a region.
    Returns None if cache is missing or expired.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        # First check if region data exists and is valid
        region_data = db.query(CachedRegionData).filter(
            CachedRegionData.region == region
        ).first()
        
        if not region_data or not is_cache_valid(region_data.cached_at):
            return None
        
        bridges = db.query(CachedBridgeLocation).filter(
            CachedBridgeLocation.region == region
        ).limit(limit).all()
        
        if not bridges:
            return None
        
        return [_cached_bridge_to_dict(b) for b in bridges]
    finally:
        if close_db:
            db.close()


def save_region_data(
    region: str,
    conditions_data: Dict,
    costs_data: Dict,
    db: Session = None
) -> CachedRegionData:
    """
    Save or update cached region data.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        # Parse condition breakdown
        condition_map = {"Good": 0, "Fair": 0, "Poor": 0, "Critical": 0, "Unknown": 0}
        percentage_map = {"Good": 0.0, "Fair": 0.0, "Poor": 0.0, "Critical": 0.0, "Unknown": 0.0}
        
        for item in conditions_data.get("condition_breakdown", []):
            condition = item.get("condition", "Unknown")
            if condition in condition_map:
                condition_map[condition] = item.get("count", 0)
                percentage_map[condition] = round(item.get("percentage", 0.0), 1)
        
        # Get or create cached record
        cached = db.query(CachedRegionData).filter(
            CachedRegionData.region == region
        ).first()
        
        now = datetime.now(timezone.utc)
        
        if cached:
            # Update existing
            cached.total_bridges = conditions_data.get("total_bridges", 0)
            cached.good_count = condition_map["Good"]
            cached.good_percentage = percentage_map["Good"]
            cached.fair_count = condition_map["Fair"]
            cached.fair_percentage = percentage_map["Fair"]
            cached.poor_count = condition_map["Poor"]
            cached.poor_percentage = percentage_map["Poor"]
            cached.critical_count = condition_map["Critical"]
            cached.critical_percentage = percentage_map["Critical"]
            cached.unknown_count = condition_map["Unknown"]
            cached.unknown_percentage = percentage_map["Unknown"]
            cached.replacement_value_billions = round(costs_data.get("replacement_value_billions", 0.0), 1)
            cached.replacement_value_millions = round(costs_data.get("replacement_value_millions", 0.0), 1)
            cached.priority_investment_millions = round(costs_data.get("priority_investment_millions", 0.0), 1)
            cached.data_source = conditions_data.get("data_source", "Statistics Canada")
            cached.statcan_table_id = costs_data.get("statcan_table_id")
            cached.reference_year = conditions_data.get("reference_year") or costs_data.get("reference_year")
            cached.cached_at = now
            cached.last_mcp_sync = now if conditions_data.get("mcp_source") else cached.last_mcp_sync
            cached.sync_status = "synced"
            cached.sync_error = None
        else:
            # Create new
            cached = CachedRegionData(
                region=region,
                total_bridges=conditions_data.get("total_bridges", 0),
                good_count=condition_map["Good"],
                good_percentage=percentage_map["Good"],
                fair_count=condition_map["Fair"],
                fair_percentage=percentage_map["Fair"],
                poor_count=condition_map["Poor"],
                poor_percentage=percentage_map["Poor"],
                critical_count=condition_map["Critical"],
                critical_percentage=percentage_map["Critical"],
                unknown_count=condition_map["Unknown"],
                unknown_percentage=percentage_map["Unknown"],
                replacement_value_billions=round(costs_data.get("replacement_value_billions", 0.0), 1),
                replacement_value_millions=round(costs_data.get("replacement_value_millions", 0.0), 1),
                priority_investment_millions=round(costs_data.get("priority_investment_millions", 0.0), 1),
                data_source=conditions_data.get("data_source", "Statistics Canada"),
                statcan_table_id=costs_data.get("statcan_table_id"),
                reference_year=conditions_data.get("reference_year") or costs_data.get("reference_year"),
                cached_at=now,
                last_mcp_sync=now if conditions_data.get("mcp_source") else None,
                sync_status="synced"
            )
            db.add(cached)
        
        db.commit()
        db.refresh(cached)
        return cached
    finally:
        if close_db:
            db.close()


def save_bridge_locations(region: str, bridges: List[Dict], db: Session = None) -> int:
    """
    Save bridge locations for a region.
    Clears existing bridges for the region first.
    Returns number of bridges saved.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        # Delete existing bridges for this region
        db.query(CachedBridgeLocation).filter(
            CachedBridgeLocation.region == region
        ).delete()
        
        now = datetime.now(timezone.utc)
        count = 0
        
        for bridge in bridges:
            cached_bridge = CachedBridgeLocation(
                region=region,
                bridge_id=bridge.get("id", f"{region[:3].upper()}-{count+1:04d}"),
                name=bridge.get("name", f"Bridge #{count+1}"),
                latitude=float(bridge.get("latitude", 0)),
                longitude=float(bridge.get("longitude", 0)),
                condition=bridge.get("condition", "Unknown"),
                condition_index=str(bridge.get("condition_index", "")) if bridge.get("condition_index") else None,
                year_built=str(bridge.get("year_built", "")) if bridge.get("year_built") else None,
                last_inspection=bridge.get("last_inspection"),
                highway=bridge.get("highway"),
                structure_type=bridge.get("structure_type"),
                category=bridge.get("category"),
                material=bridge.get("material"),
                owner=bridge.get("owner"),
                status=bridge.get("status"),
                county=bridge.get("county"),
                source=bridge.get("source"),
                cached_at=now
            )
            db.add(cached_bridge)
            count += 1
        
        db.commit()
        return count
    finally:
        if close_db:
            db.close()


def log_sync_start(region: str, sync_type: str, db: Session = None) -> DataSyncLog:
    """Start a sync log entry"""
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        log = DataSyncLog(
            region=region,
            sync_type=sync_type,
            started_at=datetime.now(timezone.utc),
            status="in_progress"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    finally:
        if close_db:
            db.close()


def log_sync_complete(
    log_id: int,
    status: str,
    records_synced: int = 0,
    error_message: str = None,
    response_time_ms: int = None,
    db: Session = None
):
    """Complete a sync log entry"""
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        log = db.query(DataSyncLog).filter(DataSyncLog.id == log_id).first()
        if log:
            log.completed_at = datetime.now(timezone.utc)
            log.status = status
            log.records_synced = records_synced
            log.error_message = error_message
            log.mcp_response_time_ms = response_time_ms
            db.commit()
    finally:
        if close_db:
            db.close()


def get_cache_status(region: str = None, db: Session = None) -> Dict:
    """
    Get cache status for a region or all regions.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        if region:
            cached = db.query(CachedRegionData).filter(
                CachedRegionData.region == region
            ).first()
            
            if not cached:
                return {
                    "region": region,
                    "cached": False,
                    "valid": False,
                    "message": "No cached data"
                }
            
            valid = is_cache_valid(cached.cached_at)
            age_hours = 0
            if cached.cached_at:
                now = datetime.now(timezone.utc)
                cached_at = cached.cached_at.replace(tzinfo=timezone.utc) if cached.cached_at.tzinfo is None else cached.cached_at
                age_hours = round((now - cached_at).total_seconds() / 3600, 1)
            
            return {
                "region": region,
                "cached": True,
                "valid": valid,
                "cached_at": cached.cached_at.isoformat() if cached.cached_at else None,
                "age_hours": age_hours,
                "ttl_hours": CACHE_TTL_HOURS,
                "expires_in_hours": round(max(0, CACHE_TTL_HOURS - age_hours), 1),
                "sync_status": cached.sync_status,
                "total_bridges": cached.total_bridges
            }
        else:
            # Get status for all regions
            all_cached = db.query(CachedRegionData).all()
            regions_status = []
            
            for cached in all_cached:
                valid = is_cache_valid(cached.cached_at)
                age_hours = 0
                if cached.cached_at:
                    now = datetime.now(timezone.utc)
                    cached_at = cached.cached_at.replace(tzinfo=timezone.utc) if cached.cached_at.tzinfo is None else cached.cached_at
                    age_hours = round((now - cached_at).total_seconds() / 3600, 1)
                
                regions_status.append({
                    "region": cached.region,
                    "valid": valid,
                    "age_hours": age_hours,
                    "sync_status": cached.sync_status
                })
            
            return {
                "total_cached_regions": len(all_cached),
                "ttl_hours": CACHE_TTL_HOURS,
                "regions": regions_status
            }
    finally:
        if close_db:
            db.close()


def invalidate_cache(region: str = None, db: Session = None) -> int:
    """
    Invalidate cache for a region or all regions.
    Returns number of regions invalidated.
    """
    close_db = False
    if db is None:
        db = get_db_session()
        close_db = True
    
    try:
        if region:
            # Delete specific region
            count = db.query(CachedRegionData).filter(
                CachedRegionData.region == region
            ).delete()
            db.query(CachedBridgeLocation).filter(
                CachedBridgeLocation.region == region
            ).delete()
        else:
            # Delete all
            count = db.query(CachedRegionData).delete()
            db.query(CachedBridgeLocation).delete()
        
        db.commit()
        return count
    finally:
        if close_db:
            db.close()


def _cached_region_to_dict(cached: CachedRegionData) -> Dict:
    """Convert CachedRegionData to dictionary format"""
    # Calculate age for display
    age_hours = 0
    if cached.cached_at:
        now = datetime.now(timezone.utc)
        cached_at = cached.cached_at.replace(tzinfo=timezone.utc) if cached.cached_at.tzinfo is None else cached.cached_at
        age_hours = round((now - cached_at).total_seconds() / 3600, 1)
    
    return {
        "region": cached.region,
        "total_bridges": cached.total_bridges,
        "condition_breakdown": [
            {"condition": "Good", "count": cached.good_count, "percentage": cached.good_percentage},
            {"condition": "Fair", "count": cached.fair_count, "percentage": cached.fair_percentage},
            {"condition": "Poor", "count": cached.poor_count, "percentage": cached.poor_percentage},
            {"condition": "Critical", "count": cached.critical_count, "percentage": cached.critical_percentage},
            {"condition": "Unknown", "count": cached.unknown_count, "percentage": cached.unknown_percentage},
        ],
        "replacement_value_billions": cached.replacement_value_billions,
        "priority_investment_millions": cached.priority_investment_millions,
        "currency": "CAD",
        "last_updated": cached.cached_at.strftime("%Y-%m-%d") if cached.cached_at else None,
        "data_source": cached.data_source,
        "data_source_url": "https://www150.statcan.gc.ca/",
        "reference_year": cached.reference_year,
        "is_cached": True,
        "cache_age_hours": age_hours,
        "is_live_data": False  # Cached data is not "live"
    }


def _cached_bridge_to_dict(bridge: CachedBridgeLocation) -> Dict:
    """Convert CachedBridgeLocation to dictionary format"""
    return {
        "id": bridge.bridge_id,
        "name": bridge.name,
        "latitude": bridge.latitude,
        "longitude": bridge.longitude,
        "condition": bridge.condition,
        "condition_index": bridge.condition_index,
        "year_built": bridge.year_built,
        "last_inspection": bridge.last_inspection,
        "highway": bridge.highway,
        "structure_type": bridge.structure_type,
        "category": bridge.category,
        "material": bridge.material,
        "owner": bridge.owner,
        "status": bridge.status,
        "region": bridge.region,
        "county": bridge.county,
        "source": bridge.source
    }
