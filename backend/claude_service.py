import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

SYSTEM_PROMPT = """
You are an infrastructure data analyst helping government officials query infrastructure data.

Available data schema:
- Assets: id, name, type (bridge/road/facility), province, municipality, year_built, condition_index (0-100), daily_usage, risk_score (0-100)

When given a natural language query, return a JSON object with:
{
  "interpretation": "Human-readable explanation of what you understood",
  "filters": {
    "province": "Nova Scotia",
    "type": "bridge",
    "risk_score_min": 70
  },
  "sort_by": "risk_score",
  "limit": 20
}

Be precise and only include filters that are explicitly requested or strongly implied.
"""

def interpret_query(query: str):
    try:
        # Use Gemini 3  Flash for speed and efficiency
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
             return {
                "interpretation": "Mock Interpretation (Gemini): Searching for assets in Nova Scotia (API Key missing/invalid)",
                "filters": {
                    "province": "Nova Scotia"
                },
                "limit": 10
            }
            
        return {
            "interpretation": "Error processing query. Please try again.",
            "filters": {},
            "error": str(e)
        }
