"""
PRISM AI Agent Service

This service provides an intelligent conversational agent that can:
- Answer questions about infrastructure data
- Query bridges, roads, and assets
- Provide funding optimization insights
- Forecast road degradation
- Generate reports and summaries

Uses Google Gemini for natural language understanding and generation.
"""

import os
import json
from typing import Generator, List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

# Import PRISM services
import government_data_service
import funding_optimizer_service
import road_degradation_service
from database import SessionLocal
import models

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

@dataclass
class ToolCall:
    name: str
    arguments: Dict[str, Any]
    result: Any = None


class PRISMAgent:
    """
    PRISM Infrastructure Intelligence Agent
    
    An AI agent that can query and analyze Canadian infrastructure data,
    provide funding optimization recommendations, and forecast road conditions.
    """
    
    SYSTEM_PROMPT = """You are PRISM, an AI infrastructure analyst for Canadian government officials.

You have access to real government infrastructure data and can help with:
1. Finding bridge conditions and locations across Canada
2. Finding road conditions and pavement data
3. Optimizing infrastructure funding allocation
4. Forecasting road degradation over time
5. Analyzing infrastructure risks

AVAILABLE TOOLS:
- get_bridges: Get bridge data for a province (params: province, condition, limit)
- get_roads: Get road condition data (params: province, highway, limit)
- optimize_funding: Get AI-optimized funding allocation (params: region, budget)
- get_high_risk_infrastructure: Get all high-risk bridges and roads (params: region)
- forecast_road_degradation: Predict road condition over time (params: highway, province, years)
- get_infrastructure_summary: Get summary statistics for a region (params: region)

When you need to call a tool, respond with a JSON object:
{"tool": "tool_name", "params": {...}}

After receiving tool results, provide a helpful analysis. Use markdown formatting for clarity.
Be concise but thorough. Always cite specific data points in your response.

For funding questions, explain the Risk-to-Cost Ratio (RCR) algorithm that prioritizes 
infrastructure with the highest risk reduction per dollar spent.

Current date: """ + datetime.now().strftime("%B %d, %Y")

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=self.SYSTEM_PROMPT
        )
        self.chat = self.model.start_chat(history=[])
        self.db = SessionLocal()
        
    def _get_bridges(self, province: str = "Ontario", condition: Optional[str] = None, limit: int = 50) -> Dict:
        """Get bridge data from MCP cache or live API"""
        bridges = government_data_service.get_bridge_locations(province, limit=limit * 2)
        
        if bridges and condition:
            bridges = [b for b in bridges if b.get("condition", "").lower() == condition.lower()]
        
        bridges = bridges[:limit] if bridges else []
        
        # Summarize
        conditions = {}
        for b in bridges:
            cond = b.get("condition", "Unknown")
            conditions[cond] = conditions.get(cond, 0) + 1
            
        return {
            "province": province,
            "total_found": len(bridges),
            "condition_summary": conditions,
            "bridges": bridges[:20],  # Return top 20 for display
            "filter_applied": condition
        }
    
    def _get_roads(self, province: str = "Ontario", highway: Optional[str] = None, limit: int = 50) -> Dict:
        """Get road condition data"""
        try:
            query = self.db.query(models.CachedRoadCondition).filter(
                models.CachedRoadCondition.province == province
            )
            
            if highway:
                query = query.filter(models.CachedRoadCondition.highway.ilike(f"%{highway}%"))
            
            roads = query.limit(limit).all()
            
            # Summarize conditions
            conditions = {}
            total_km = 0
            for r in roads:
                cond = r.condition or "Unknown"
                conditions[cond] = conditions.get(cond, 0) + 1
                if r.km_start is not None and r.km_end is not None:
                    total_km += abs(r.km_end - r.km_start)
            
            road_list = [
                {
                    "highway": r.highway,
                    "condition": r.condition,
                    "pci": r.pci,
                    "km_start": r.km_start,
                    "km_end": r.km_end,
                    "pavement_type": r.pavement_type,
                    "aadt": r.aadt
                }
                for r in roads[:20]
            ]
            
            return {
                "province": province,
                "highway_filter": highway,
                "total_sections": len(roads),
                "total_km": round(total_km, 1),
                "condition_summary": conditions,
                "roads": road_list
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _optimize_funding(self, region: str = "Ontario", budget: float = 50_000_000) -> Dict:
        """Get funding optimization results"""
        try:
            service = funding_optimizer_service.get_funding_optimizer_service()
            result = service.optimize_budget(region, budget, include_roads=True)
            comparison = service.compare_approaches(region, budget)
            
            return {
                "region": region,
                "budget": f"${budget:,.0f}",
                "bridges_selected": result.total_bridges_selected,
                "roads_selected": result.total_roads_selected,
                "total_cost": f"${result.total_cost:,.0f}",
                "budget_utilization": f"{result.budget_utilization_percent}%",
                "risk_reduction": f"{result.risk_reduction_percent}%",
                "critical_bridges_funded": result.critical_bridges_funded,
                "critical_roads_funded": result.critical_roads_funded,
                "improvement_over_traditional": f"{comparison.improvement_percent}%",
                "top_bridges": [
                    {"name": b["name"], "condition": b["condition"], "cost": b["cost_display"], "risk": b["risk_score"]}
                    for b in result.selected_bridges[:5]
                ],
                "top_roads": [
                    {"highway": r["highway"], "condition": r["condition"], "cost": r["cost_display"], "risk": r["risk_score"]}
                    for r in result.selected_roads[:5]
                ],
                "warnings": result.warnings
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_high_risk_infrastructure(self, region: str = "Ontario") -> Dict:
        """Get all high-risk infrastructure"""
        try:
            service = funding_optimizer_service.get_funding_optimizer_service()
            result = service.get_all_high_risk_infrastructure(region)
            
            return {
                "region": region,
                "total_high_risk": result["total_infrastructure_count"],
                "total_critical": result["total_critical_count"],
                "total_repair_cost": f"${result['total_repair_cost']:,.0f}",
                "bridges": {
                    "count": result["bridges"]["total_high_risk_bridges"],
                    "critical": result["bridges"]["critical_bridges"],
                    "cost": f"${result['bridges']['total_repair_cost']:,.0f}"
                },
                "roads": {
                    "count": result["roads"]["total_high_risk_roads"],
                    "critical": result["roads"]["critical_roads"],
                    "cost": f"${result['roads']['total_repair_cost']:,.0f}",
                    "total_km": result["roads"].get("total_length_km", 0)
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _forecast_road_degradation(self, highway: str, province: str = "Ontario", years: int = 5) -> Dict:
        """Forecast road degradation"""
        try:
            service = road_degradation_service.RoadDegradationService()
            forecasts = service.forecast_degradation(highway, province, years=years)
            
            if not forecasts:
                return {"error": f"No data found for {highway} in {province}"}
            
            forecast_data = []
            for f in forecasts[:10]:
                forecast_data.append({
                    "section": f.section,
                    "current_pci": f.current_pci,
                    "predicted_pci": f.predicted_pci,
                    "years_to_critical": f.years_to_critical,
                    "optimal_intervention_year": f.optimal_intervention_year,
                    "cost_savings_optimal": f"${f.cost_savings_optimal:,.0f}" if f.cost_savings_optimal else "N/A"
                })
            
            return {
                "highway": highway,
                "province": province,
                "forecast_years": years,
                "sections_analyzed": len(forecasts),
                "forecasts": forecast_data
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_infrastructure_summary(self, region: str = "Ontario") -> Dict:
        """Get summary statistics for a region"""
        try:
            # Get bridge summary
            bridges = government_data_service.get_bridge_locations(region, limit=500)
            bridge_conditions = {}
            for b in bridges:
                cond = b.get("condition", "Unknown")
                bridge_conditions[cond] = bridge_conditions.get(cond, 0) + 1
            
            # Get road summary
            roads = self.db.query(models.CachedRoadCondition).filter(
                models.CachedRoadCondition.province == region
            ).all()
            
            road_conditions = {}
            total_road_km = 0
            avg_pci = []
            for r in roads:
                cond = r.condition or "Unknown"
                road_conditions[cond] = road_conditions.get(cond, 0) + 1
                if r.km_start is not None and r.km_end is not None:
                    total_road_km += abs(r.km_end - r.km_start)
                if r.pci is not None:
                    avg_pci.append(r.pci)
            
            return {
                "region": region,
                "bridges": {
                    "total": len(bridges),
                    "by_condition": bridge_conditions
                },
                "roads": {
                    "total_sections": len(roads),
                    "total_km": round(total_road_km, 1),
                    "average_pci": round(sum(avg_pci) / len(avg_pci), 1) if avg_pci else None,
                    "by_condition": road_conditions
                }
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _execute_tool(self, tool_name: str, params: Dict) -> Any:
        """Execute a tool and return results"""
        tools = {
            "get_bridges": self._get_bridges,
            "get_roads": self._get_roads,
            "optimize_funding": self._optimize_funding,
            "get_high_risk_infrastructure": self._get_high_risk_infrastructure,
            "forecast_road_degradation": self._forecast_road_degradation,
            "get_infrastructure_summary": self._get_infrastructure_summary,
        }
        
        if tool_name in tools:
            return tools[tool_name](**params)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def chat_stream(self, message: str) -> Generator[str, None, None]:
        """
        Process a chat message and stream the response.
        Yields SSE-formatted events.
        """
        try:
            # Send message to model
            response = self.chat.send_message(message)
            response_text = response.text.strip()
            
            # Check if model wants to call a tool
            max_tool_calls = 5
            tool_calls = 0
            
            while tool_calls < max_tool_calls:
                # Try to parse as JSON tool call
                try:
                    # Handle potential markdown code blocks
                    text_to_parse = response_text
                    if "```json" in text_to_parse:
                        text_to_parse = text_to_parse.split("```json")[1].split("```")[0]
                    elif "```" in text_to_parse:
                        text_to_parse = text_to_parse.split("```")[1].split("```")[0]
                    
                    tool_request = json.loads(text_to_parse.strip())
                    
                    if "tool" in tool_request:
                        tool_name = tool_request["tool"]
                        params = tool_request.get("params", {})
                        
                        # Notify client about tool call
                        yield f"data: [TOOL_START] {tool_name}\n\n"
                        
                        # Execute tool
                        result = self._execute_tool(tool_name, params)
                        
                        yield f"data: [TOOL_END] {tool_name}\n\n"
                        
                        # Send result back to model
                        result_str = json.dumps(result, indent=2, default=str)
                        response = self.chat.send_message(f"Tool result for {tool_name}:\n```json\n{result_str}\n```\n\nPlease provide a helpful analysis of this data for the user.")
                        response_text = response.text.strip()
                        tool_calls += 1
                        continue
                        
                except (json.JSONDecodeError, KeyError):
                    # Not a tool call, break and stream the response
                    pass
                
                break
            
            # Stream the final response
            # Split into chunks for smoother streaming
            words = response_text.split(' ')
            chunk_size = 3  # Words per chunk
            
            for i in range(0, len(words), chunk_size):
                chunk = ' '.join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += ' '
                yield f"data: {chunk}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
            yield "data: [DONE]\n\n"
    
    def chat_sync(self, message: str) -> str:
        """
        Process a chat message synchronously.
        Returns the complete response.
        """
        full_response = ""
        tool_calls = []
        
        for event in self.chat_stream(message):
            if event.startswith("data: "):
                data = event[6:].strip()
                if data == "[DONE]":
                    break
                elif data.startswith("[TOOL_START]"):
                    tool_calls.append(data[13:])
                elif data.startswith("[TOOL_END]"):
                    pass
                elif not data.startswith("Error:"):
                    full_response += data
        
        return full_response
    
    def reset_conversation(self):
        """Reset the conversation history"""
        self.chat = self.model.start_chat(history=[])


# Singleton instance
_agent_instance = None

def get_agent() -> PRISMAgent:
    """Get or create the PRISM agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = PRISMAgent()
    return _agent_instance

def reset_agent():
    """Reset the agent instance"""
    global _agent_instance
    _agent_instance = None
