# PRISM - Predictive Resource Intelligence for Strategic Management

PRISM is a government-grade infrastructure risk management system designed for Atlantic Canada. It leverages AI and multi-criteria optimization to help decision-makers allocate budgets effectively.

## Features

-   **Interactive Map**: Visualizes 150+ infrastructure assets with risk-based color coding.
-   **AI Risk Scoring**: Calculates risk scores (0-100) based on condition, usage, climate, redundancy, and population impact.
-   **Natural Language Query**: Ask questions like "Show critical bridges in Nova Scotia" using Claude AI.
-   **Budget Optimizer**: Allocates funding based on customizable priorities (Cost Efficiency, Equity, Resilience, Impact).
-   **Risk Dashboard**: Real-time analytics and charts.

## Tech Stack

-   **Backend**: Python 3.11+, FastAPI, SQLite, SQLAlchemy, Scikit-learn, Anthropic API.
-   **Frontend**: Next.js 14, React, Tailwind CSS, Leaflet, Recharts.

## Setup Instructions

### Prerequisites
-   Python 3.11+
-   Node.js 18+
-   Anthropic API Key (optional for mock mode)

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
    ```
5.  Start server:
    ```bash
    uvicorn main:app --reload
    ```
6.  Seed data:
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

-   `GET /api/assets`: List all assets.
-   `POST /api/risk/calculate`: Calculate risk for an asset.
-   `POST /api/query/nl`: Natural language query.
-   `POST /api/optimize`: Run budget optimization.

## Data Source
**Note**: All asset data is synthetic but generated based on realistic geographic and demographic patterns of Atlantic Canada for demonstration purposes.
