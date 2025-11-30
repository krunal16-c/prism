import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """
You are an infrastructure data analyst helping government officials query infrastructure data.

Available data sources:

1. ASSETS (internal database):
- Assets: id, name, type (bridge/road/facility), province, municipality, year_built, condition_index (0-100), daily_usage, risk_score (0-100)

2. GOVERNMENT BRIDGE DATA (Statistics Canada via MCP):
- Bridges: id, name, condition (Critical/Poor/Fair/Good/Very Good/Unknown), highway, county/area, year_built, structure_type, material, owner, last_inspection
- Available for provinces: Ontario (real data), Quebec, British Columbia, Alberta, Manitoba, Saskatchewan, Nova Scotia, New Brunswick, Newfoundland and Labrador, Prince Edward Island, Northwest Territories, Yukon, Nunavut

When given a natural language query, determine which data source to use and return a JSON object with:
{
  "interpretation": "Human-readable explanation of what you understood",
  "data_source": "bridges" or "assets",
  "filters": {
    "province": "British Columbia",
    "condition": "Critical",
    ...other relevant filters
  },
  "sort_by": "condition" or "risk_score",
  "limit": 20
}

Rules:
- If the query mentions "bridges", "bridge condition", "government data", "infrastructure condition", "Statistics Canada", or specific provinces with bridge conditions → use "bridges" data source
- If the query mentions "risk", "risk score", "assets", "facilities", "roads" → use "assets" data source
- For bridge queries, valid conditions are: Critical, Poor, Fair, Good, Very Good, Unknown
- Be precise and only include filters that are explicitly requested or strongly implied.
- When a province/region is mentioned, extract it as "province" filter
- When a condition is mentioned (critical, poor, fair, good), extract it as "condition" filter
"""

def interpret_query(query: str):
    try:
        # Use Gemini 2.5 Flash for speed and efficiency
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json"}
        )
        
        response = model.generate_content(query)
        
        content = response.text
        # Gemini with JSON mode usually returns clean JSON, but safety check
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        # Mock response for demo/testing if API fails (e.g. no key)
        if "401" in str(e) or "API_KEY_INVALID" in str(e) or "default" in str(e).lower():
            # Smart fallback based on query content
            query_lower = query.lower()
            
            # Detect if it's a bridge query
            if any(word in query_lower for word in ['bridge', 'bridges', 'infrastructure condition', 'government data']):
                # Extract province if mentioned
                provinces = {
                    'ontario': 'Ontario', 'quebec': 'Quebec', 'british columbia': 'British Columbia',
                    'bc': 'British Columbia', 'alberta': 'Alberta', 'manitoba': 'Manitoba',
                    'saskatchewan': 'Saskatchewan', 'nova scotia': 'Nova Scotia',
                    'new brunswick': 'New Brunswick', 'pei': 'Prince Edward Island',
                    'newfoundland': 'Newfoundland and Labrador'
                }
                province = None
                for key, val in provinces.items():
                    if key in query_lower:
                        province = val
                        break
                
                # Extract condition if mentioned
                conditions = {'critical': 'Critical', 'poor': 'Poor', 'fair': 'Fair', 'good': 'Good'}
                condition = None
                for key, val in conditions.items():
                    if key in query_lower:
                        condition = val
                        break
                
                filters = {}
                if province:
                    filters['province'] = province
                if condition:
                    filters['condition'] = condition
                
                return {
                    "interpretation": f"Searching for {'condition-filtered ' if condition else ''}bridges{' in ' + province if province else ''} (API Key missing - using fallback)",
                    "data_source": "bridges",
                    "filters": filters,
                    "limit": 100
                }
            
            return {
                "interpretation": "Mock Interpretation (Gemini): Searching for assets in Nova Scotia (API Key missing/invalid)",
                "data_source": "assets",
                "filters": {
                    "province": "Nova Scotia"
                },
                "limit": 10
            }
            
        return {
            "interpretation": "Error processing query. Please try again.",
            "data_source": "assets",
            "filters": {},
            "error": str(e)
        }
