# PRISM AI Agent - Government Infrastructure Intelligence

The PRISM AI Agent is an intelligent conversational interface for querying Canadian government infrastructure data. Built with LangChain and OpenAI GPT-4, it connects to MCP (Model Context Protocol) servers to access real-time data from Government of Canada open data portals.

## Features

### 🤖 Natural Language Interface
- Ask questions about infrastructure in plain English
- Get intelligent responses with data-backed insights
- Streaming responses for real-time feedback

### 🔧 MCP Tool Integration
- Dynamically discovers and uses tools from connected MCP servers
- Supports multiple data sources simultaneously
- Automatic schema conversion to LangChain tools

### 📊 Data Processing Capabilities
- Download datasets directly from government portals
- Extract and analyze CSV/JSON files
- Process ZIP archives automatically

### 🎯 Infrastructure Focus
- Bridge condition analysis
- Road degradation forecasting
- Funding optimization insights
- Regional infrastructure statistics

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                    ChatInterface.tsx                         │
└─────────────────────────┬───────────────────────────────────┘
                          │ POST /chat (SSE Stream)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  AI Agent Service (Port 8080)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   api.py    │──│  agent.py   │──│  AgentManager       │  │
│  │  (FastAPI)  │  │ (LangChain) │  │  - MCP Connections  │  │
│  └─────────────┘  └─────────────┘  │  - Tool Discovery   │  │
│                                     │  - GPT-4 Agent      │  │
│                                     └─────────────────────┘  │
└────────────────┬────────────────────────────┬───────────────┘
                 │                            │
     ┌───────────▼───────────┐    ┌──────────▼──────────┐
     │ MCP Transportation    │    │    MCP Gov Data     │
     │   (Port 8001/SSE)     │    │   (Port 8002/SSE)   │
     │  - Road conditions    │    │  - Dataset search   │
     │  - Bridge data        │    │  - Organizations    │
     │  - Pavement metrics   │    │  - Activity streams │
     └───────────────────────┘    └─────────────────────┘
```

## Prerequisites

1. **Python 3.10+** (3.12 recommended)
2. **OpenAI API Key** with GPT-4 access
3. **MCP Servers** (optional but recommended):
   - `gov_ca_transportation` on port **8001** (SSE)
   - `gov_mcp` on port **8002** (SSE)

## Installation

### 1. Create Virtual Environment

```bash
cd gov_agents
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```env
OPENAI_API_KEY=sk-your-openai-api-key
```

## Running the Agent

### Option 1: Run as API Service (Recommended)

```bash
# Start the API server on port 8080
uvicorn main:app --reload --port 8080
```

The API will be available at `http://localhost:8080`

### Option 2: Run as CLI Agent

```bash
python agent.py
```

This starts an interactive command-line interface.

## API Endpoints

### POST /chat
Streaming chat endpoint that returns Server-Sent Events (SSE).

**Request:**
```json
{
  "message": "Show me poor condition bridges in Ontario"
}
```

**Response (SSE Stream):**
```
data: [TOOL_START] search_datasets: {'query': 'bridges Ontario'}

data: Based on my analysis...

data: [TOOL_END] search_datasets

data: [DONE]
```

### GET /health
Check agent initialization status.

**Response:**
```json
{
  "status": "ok",
  "agent_initialized": true
}
```

## Tools

### MCP Tools (Dynamic)
Tools are automatically discovered from connected MCP servers:

| Tool | Source | Description |
|------|--------|-------------|
| `search_datasets` | gov_mcp | Search Government of Canada datasets |
| `get_dataset_schema` | gov_mcp | Get dataset structure and resources |
| `list_organizations` | gov_mcp | List government organizations |
| `get_activity_stream` | gov_mcp | Get recent data activity |
| `get_bridge_conditions` | transportation | Query bridge condition data |
| `get_road_conditions` | transportation | Query road pavement data |

### Local Tools
Built-in tools for file operations:

| Tool | Description |
|------|-------------|
| `download_file` | Download files from URLs |
| `unzip_file` | Extract ZIP archives |
| `read_csv_head` | Preview CSV file contents |
| `list_files` | List directory contents |

## Example Queries

### Infrastructure Analysis
```
"What bridges in Ontario are in poor condition?"
"Show me the worst roads on Highway 401"
"Compare bridge conditions between Ontario and Quebec"
```

### Funding & Planning
```
"Optimize a $50M budget for infrastructure repairs"
"What's the economic impact of poor road conditions?"
"Which regions need the most urgent repairs?"
```

### Data Discovery
```
"Find datasets about transportation infrastructure"
"Download the latest bridge inspection data"
"Show me traffic volume statistics"
```

## Agent Workflow

The agent follows a structured workflow for data queries:

1. **Search** - Use `search_datasets` to find relevant datasets
2. **Investigate** - Use `get_dataset_schema` to understand data structure
3. **Decide** - Analyze schema to select the best resource (CSV, JSON, ZIP)
4. **Download** - Use `download_file` to retrieve the data
5. **Process** - Use `unzip_file` if needed, then `read_csv_head`
6. **Analyze** - Interpret the data and provide insights
7. **Respond** - Give a comprehensive answer with citations

## Frontend Integration

The ChatInterface component connects to this agent:

```typescript
// ChatInterface.tsx
const response = await fetch("http://localhost:8080/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message: userMessage }),
});

// Read SSE stream
const reader = response.body.getReader();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // Process streaming chunks...
}
```

## Configuration

### MCP Server URLs
Edit `agent.py` to change MCP server endpoints:

```python
MCP_SERVERS = [
    "http://localhost:8001/sse",  # Transportation data
    "http://localhost:8002/sse"   # Gov open data
]
```

### LLM Model
Change the model in `agent.py`:

```python
llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0)
```

### CORS Origins
Update `api.py` for different frontend ports:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    ...
)
```

## Troubleshooting

### Agent Not Initialized
```
Error: Agent not initialized
```
**Solution:** Ensure MCP servers are running, or the agent will start with limited tools.

### MCP Connection Failed
```
Failed to connect to http://localhost:8001/sse
```
**Solution:** Start the MCP servers before running the agent.

### OpenAI API Error
```
OPENAI_API_KEY environment variable is not set
```
**Solution:** Add your API key to `.env` file.

### Tool Execution Error
```
Error calling tool search_datasets: ...
```
**Solution:** Check MCP server logs for detailed error messages.

## File Structure

```
gov_agents/
├── .env                 # Environment variables (API keys)
├── agent.py             # LangChain agent with MCP integration
├── api.py               # FastAPI streaming endpoint
├── main.py              # Entry point for uvicorn
├── requirements.txt     # Python dependencies
├── test_connection.py   # MCP connection tester
├── tools/
│   ├── __init__.py
│   └── file_ops.py      # Local file operation tools
└── downloads/           # Downloaded files (auto-created)
```

## Dependencies

```
mcp                      # Model Context Protocol client
httpx                    # Async HTTP client
httpx-sse                # SSE client support
pandas                   # Data processing
langchain==0.3.0         # Agent framework
langchain-core==0.3.0    # Core abstractions
langchain-openai==0.2.0  # OpenAI integration
langchain-community==0.3.0
python-dotenv            # Environment management
fastapi                  # Web framework
uvicorn                  # ASGI server
tabulate                 # Table formatting
```

## Related Documentation

- [PRISM Main README](../README.md)
- [Funding Optimizer Documentation](../documentation/FUNDING_SCENARIO_OPTIMIZER.md)
- [Backend API Documentation](../backend/README.md)

*   **Connection Error**: If the agent says "Failed to connect", ensure the MCP servers are running with the `--sse` flag and on the correct ports.
*   **API Key Error**: Ensure `OPENAI_API_KEY` is set.
