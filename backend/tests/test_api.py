from fastapi.testclient import TestClient
from main import app
from crud import get_assets, create_risk_score
from schemas import AssetCreate
import pytest

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "PRISM API"}

def test_seed_data():
    # Ensure database is clean or handle existing data
    response = client.post("/api/seed")
    assert response.status_code == 200
    assert "Seeded" in response.json()["message"] or "already seeded" in response.json()["message"]

def test_get_assets():
    response = client.get("/api/assets")
    assert response.status_code == 200
    assets = response.json()
    assert isinstance(assets, list)
    assert len(assets) > 0

def test_risk_calculation():
    # Get an asset first
    assets = client.get("/api/assets").json()
    asset_id = assets[0]["id"]
    
    response = client.post("/api/risk/calculate", json={"asset_id": asset_id})
    assert response.status_code == 200
    data = response.json()
    assert "overall_score" in data
    assert 0 <= data["overall_score"] <= 100

def test_nl_query():
    response = client.post("/api/query/nl", json={"query": "Show me bridges in Nova Scotia"})
    assert response.status_code == 200
    data = response.json()
    assert "interpretation" in data
    # Check if mock or real response structure is present
    assert "filters" in data

def test_optimize():
    response = client.post("/api/optimize", json={
        "budget": 500000000,
        "priorities": {
            "cost_efficiency": 50,
            "regional_equity": 50,
            "climate_resilience": 50,
            "population_impact": 50
        }
    })
    assert response.status_code == 200
    data = response.json()
    assert data["total_budget"] == 500000000
    assert len(data["allocations"]) > 0
