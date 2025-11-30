# Feature 1: Live Government Data Dashboard

**Feature ID:** F1-DASHBOARD  
**Priority:** P0 (CRITICAL - Must Have)  
**Status:** ✅ Implemented with Live MCP Integration

---

## Overview

The Live Government Data Dashboard provides real-time infrastructure statistics for Canadian provinces, displaying bridge conditions, replacement values, and priority investment data. The system integrates with Government of Canada MCP Servers via SSE (Server-Sent Events) for live data from Statistics Canada, with automatic fallback to cached data when servers are unavailable.

---

## MCP Server Integration

### Connected MCP Servers

| Server | Port | SSE Endpoint | Purpose |
|--------|------|--------------|---------|
| Dataset MCP | 9000 | `/sse` | Dataset discovery and search (250,000+ datasets) |
| Transportation MCP | 9001 | `/sse` | Bridge conditions, infrastructure costs |

### Data Sources

| StatCan Table ID | Description |
|-----------------|-------------|
| 34-10-0288-01 | Physical condition of core public infrastructure |
| 34-10-0284-01 | Estimated replacement value of core public infrastructure |

### Environment Variables

```bash
# MCP Server URLs (optional, defaults shown)
MCP_TRANSPORTATION_URL=http://localhost:9001/sse
MCP_DATASET_URL=http://localhost:9000/sse

# Enable/disable live MCP data (default: true)
USE_LIVE_MCP=true
```

### Data Flow

```
Frontend Request
      ↓
  Backend API (FastAPI)
      ↓
┌─────────────────────┐
│ MCP SSE Client      │ ──→ Live Statistics Canada Data
│ (mcp SDK v1.22.0)   │     via analyze_bridge_conditions,
│                     │     get_infrastructure_costs,
│                     │     query_bridges tools
└─────────────────────┘
      ↓ (if unavailable)
┌─────────────────────┐
│ Fallback to         │ ──→ Cached Statistics Canada Data
│ Local Cache         │     (all 13 provinces/territories)
└─────────────────────┘
      ↓
  Dashboard Response (JSON)
```

---

## Files Created/Modified

### Backend

| File | Type | Description |
|------|------|-------------|
| `backend/mcp_client.py` | New | Async MCP SSE client using official SDK |
| `backend/government_data_service.py` | New | MCP integration with fallback data |
| `backend/main.py` | Modified | Added 7 dashboard API endpoints |

### Frontend

| File | Type | Description |
|------|------|-------------|
| `frontend/components/GovernmentDashboard.tsx` | New | Main dashboard component (535 lines) |
| `frontend/components/GovernmentMap.tsx` | New | Interactive Leaflet map for bridges |
| `frontend/types.ts` | Modified | Added TypeScript interfaces |
| `frontend/app/page.tsx` | Modified | Added navigation item |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard/regions` | GET | List all 13 supported provinces/territories |
| `/api/dashboard/summary/{region}` | GET | Comprehensive dashboard data for a region |
| `/api/dashboard/bridges/{region}` | GET | Bridge locations for map display |
| `/api/dashboard/national` | GET | Aggregated national statistics |
| `/api/dashboard/conditions/{region}` | GET | Detailed condition breakdown |
| `/api/dashboard/costs/{region}` | GET | Infrastructure cost data |
| `/api/mcp/status` | GET | Check MCP server connection status with tool list |

---

## MCP Tools Used

### Transportation MCP (port 9001)

| Tool | Usage |
|------|-------|
| `analyze_bridge_conditions` | Get condition percentages from StatCan 34-10-0288-01 |
| `get_infrastructure_costs` | Get replacement values from StatCan 34-10-0284-01 |
| `query_bridges` | Get individual bridge records with coordinates |
| `compare_across_regions` | Compare infrastructure across provinces |

### Dataset MCP (port 9000)

| Tool | Usage |
|------|-------|
| `search_datasets` | Search 250,000+ government datasets |
| `get_dataset_schema` | Get field definitions and download URLs |
| `browse_by_topic` | Explore datasets by subject area |

### Dataset MCP (`gov_mcp`)

| Tool | Usage |
|------|-------|
| `search_datasets` | Search infrastructure datasets |
| `browse_by_topic` | Browse by infrastructure topics |

---

## Functional Requirements Implementation

### FR-1.1: Region Overview Display ✅

**Data Points Displayed:**
- Total number of bridges in region
- Condition breakdown (Good, Fair, Poor, Critical, Unknown) with counts and percentages
- Total replacement value in billions (CAD)
- Priority investment needed amount
- Last data update timestamp

**Default Region:** Ontario  
**Supported Regions:** All 13 Canadian provinces and territories

### FR-1.2: Region Selection ✅

- Dropdown menu with all provinces
- Dashboard data refreshes on region change
- URL updates with region parameter (`?region=Quebec`)
- Error handling for regions with no data

### FR-1.3: Visual Data Representation ✅

- **Metric Cards:** Large numeric displays for key metrics
- **Pie Chart:** Condition breakdown with percentages
- **Color Coding:**
  - Good: Green (`#22c55e`)
  - Fair: Yellow (`#eab308`)
  - Poor: Orange (`#f97316`)
  - Critical: Red (`#ef4444`)
  - Unknown: Slate (`#94a3b8`)
- **Interactive Map:** Bridge locations as colored dots
- **Data Source Badge:** Statistics Canada attribution

### FR-1.4: Data Currency Indicator ✅

- Format: `Last Updated: YYYY-MM-DD`
- Source: "Statistics Canada • Official Government Data"
- Placement: Bottom footer, always visible
- External link to data source

---

## Non-Functional Requirements Implementation

### NFR-1.1: Performance ✅

- Parallel API calls for summary and bridge data
- Memoized map markers for performance
- Dynamic imports for map component (code splitting)

### NFR-1.2: Accessibility ✅

- **ARIA Labels:** All interactive elements properly labeled
- **Screen Reader Support:**
  - Hidden data tables for chart content
  - Descriptive text for map
  - Proper heading hierarchy
- **Keyboard Navigation:**
  - Tab navigation through all elements
  - Escape key closes modal/dropdown
  - Enter/Space activates buttons
- **Focus Indicators:** Visible focus rings on all interactive elements

### NFR-1.3: Responsive Design ✅

- Grid layout adapts to screen size
- Cards stack on mobile
- Map remains functional at all sizes

### NFR-1.4: Data Integrity ✅

- Data displayed matches source exactly
- Clear distinction between actual and calculated values
- Source attribution on all data

---

## Component Structure

```
GovernmentDashboard
├── Header
│   ├── Title & Description
│   ├── Region Selector (Dropdown)
│   └── Close Button
├── Main Content
│   ├── Metric Cards (4)
│   │   ├── Total Bridges
│   │   ├── Critical Condition
│   │   ├── Replacement Value
│   │   └── Priority Investment
│   ├── Condition Breakdown (Pie Chart)
│   └── Map Section
│       ├── GovernmentMap
│       └── Legend
└── Footer
    ├── Data Source Badge
    └── Last Updated Date
```

---

## Data Model

### DashboardSummary
```typescript
interface DashboardSummary {
  region: string;
  total_bridges: number;
  condition_breakdown: ConditionBreakdown[];
  replacement_value_billions: number;
  priority_investment_millions: number;
  currency: string;
  last_updated: string;
  data_source: string;
  data_source_url?: string;
}
```

### BridgeLocation
```typescript
interface BridgeLocation {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  condition: string;
  year_built: number;
  last_inspection: string;
  region: string;
}
```

---

## Usage

1. Click "Gov Data Dashboard" in the sidebar navigation
2. Dashboard opens with Ontario data (default)
3. Use dropdown to select different province
4. View metrics, charts, and map
5. Click bridge markers on map for details
6. Press Escape or click X to close

---

## Testing Checklist

- [ ] UAT-1.1: Dashboard loads within 5 seconds with Ontario data
- [ ] UAT-1.2: Region switching loads new data within 3 seconds
- [ ] UAT-1.3: Pie chart percentages sum to 100%
- [ ] UAT-1.4: Map displays bridges with correct colors
- [ ] UAT-1.5: Screen reader announces all content properly
