# PRISM - Predictive Resource Intelligence for Strategic Management

PRISM is a government-grade infrastructure risk management system designed for Canadian provinces. It leverages AI, MCP (Model Context Protocol) integration, and multi-criteria optimization to help decision-makers allocate budgets effectively for road infrastructure maintenance.

## Features

### Core Features
-   **Live Government Data Dashboard**: Real-time infrastructure statistics from Statistics Canada with province selection, condition breakdowns, and interactive maps.
-   **Interactive Map**: Visualizes infrastructure assets with risk-based color coding.
-   **AI Risk Scoring**: Calculates risk scores (0-100) based on condition, usage, climate, redundancy, and population impact.
-   **Natural Language Query**: Ask questions like "Show critical bridges in Nova Scotia" using Claude AI.
-   **Budget Optimizer**: Allocates funding based on customizable priorities (Cost Efficiency, Equity, Resilience, Impact).
-   **Risk Dashboard**: Real-time analytics and charts.

### Highway Degradation Forecaster (Feature 10)
-   **PCI Degradation Prediction**: Forecasts Pavement Condition Index (PCI) deterioration over 1-10 years
-   **Climate-Adjusted Models**: Accounts for freeze-thaw cycles, regional climate zones, and seasonal factors
-   **Traffic Impact Analysis**: Factors in AADT (Annual Average Daily Traffic) for degradation acceleration
-   **Optimal Intervention Timing**: Identifies cost-effective maintenance windows
-   **Economic Impact Calculator**: Quantifies vehicle damage, fuel waste, and freight delay costs

### Winter Resilience Predictor (Feature 11)
-   **Freeze-Thaw Vulnerability Scoring**: Predicts which road sections will suffer worst winter damage
-   **Pre-Winter Intervention Calculator**: ROI analysis for preventive vs reactive maintenance
-   **Climate Zone Mapping**: Province-specific freeze-thaw cycle predictions
-   **Threshold Crossing Alerts**: Identifies sections at risk of condition downgrades

### Corridor Optimization (Feature 12)
-   **Multi-Section Bundling**: Groups adjacent repair sections for mobilization cost savings (15-25%)
-   **Directional Analysis**: Compares eastbound vs westbound condition differences
-   **Federal Funding Qualification**: Identifies bundles meeting $20M+ thresholds
-   **Traffic Disruption Minimization**: Optimizes repair scheduling to reduce closures

## Tech Stack

-   **Backend**: Python 3.11+, FastAPI, SQLite, SQLAlchemy, Scikit-learn, Anthropic API
-   **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS, Leaflet, Recharts
-   **Data Integration**: MCP (Model Context Protocol) for real-time road condition data
-   **Database**: SQLite with 24-hour caching for MCP data

## Setup Instructions

### Prerequisites
-   Python 3.11+
-   Node.js 18+
-   Anthropic API Key (optional for mock mode)
-   MCP Transportation Server (optional - falls back to generated data)

### Backend Setup
1.  Navigate to `backend`:
    ```bash
    cd backend
    ```
2.  Create virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Set environment variables in `.env`:
    ```
    ANTHROPIC_API_KEY=your_key
    DATABASE_URL=sqlite:///./prism.db
    MCP_TRANSPORTATION_URL=http://localhost:8001/sse
    ```
5.  Start server:
    ```bash
    uvicorn main:app --reload
    ```
6.  Seed data (optional):
    ```bash
    curl -X POST http://localhost:8000/api/seed
    ```

### Frontend Setup
1.  Navigate to `frontend`:
    ```bash
    cd frontend
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start dev server:
    ```bash
    npm run dev
    ```
4.  Open [http://localhost:3000](http://localhost:3000).

## API Documentation

### Core APIs
-   `GET /api/assets`: List all assets.
-   `POST /api/risk/calculate`: Calculate risk for an asset.
-   `POST /api/query/nl`: Natural language query.
-   `POST /api/optimize`: Run budget optimization.

### Government Dashboard APIs
-   `GET /api/dashboard/regions`: Get list of all supported provinces.
-   `GET /api/dashboard/summary/{region}`: Get comprehensive dashboard data for a region.
-   `GET /api/dashboard/bridges/{region}`: Get bridge locations for map display.
-   `GET /api/dashboard/national`: Get aggregated national statistics.
-   `GET /api/dashboard/conditions/{region}`: Get detailed condition breakdown.
-   `GET /api/dashboard/costs/{region}`: Get infrastructure cost data.

### Highway Degradation APIs (Feature 10)
-   `GET /api/roads/conditions`: Get road condition data with PCI, DMI, IRI metrics
-   `GET /api/roads/highways/{province}`: Get available highways for a province
-   `GET /api/roads/forecast/{highway}`: Get degradation forecast for a highway
-   `GET /api/roads/economic-impact`: Calculate economic impact of road conditions
-   `GET /api/roads/heatmap`: Get network heatmap visualization data

### Winter Resilience APIs (Feature 11)
-   `GET /api/roads/winter/vulnerability`: Get freeze-thaw vulnerability analysis
-   `GET /api/roads/winter/forecast-summary`: Get winter damage forecast summary
-   `GET /api/roads/winter/interventions`: Get pre-winter intervention recommendations

### Corridor Optimization APIs (Feature 12)
-   `GET /api/roads/corridor/bundles`: Get multi-section repair bundles
-   `GET /api/roads/corridor/directional-analysis`: Get directional condition comparison
-   `GET /api/roads/corridor/summary`: Get corridor optimization summary

## Data Sources

### MCP Integration
PRISM integrates with the Transportation MCP Server for real-time Ontario road condition data:
-   **1,819 road sections** cached from MCP
-   **259 unique highways** including 401, QEW, 400-series, and provincial routes
-   **Metrics**: PCI, DMI, IRI, pavement type, coordinates, functional class

### Caching Strategy
-   Road condition data is cached in SQLite with 24-hour TTL
-   Automatic fallback to generated data if MCP is unavailable
-   Field normalization handles MCP naming conventions (from_km → km_start, etc.)

### Data Quality
-   **87.9%** of records have kilometer markers
-   **73.0%** have GPS coordinates
-   **99.9%** have PCI values

**Note**: When MCP is unavailable, realistic synthetic data is generated based on Canadian highway patterns for demonstration purposes.
