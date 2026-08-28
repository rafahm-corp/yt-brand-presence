import os
import json
import configparser
import time
import re
from google import genai
from google.genai import types
from dotenv import load_dotenv

from client_factory import create_genai_client, generate_content_with_retry

from pydantic import BaseModel, Field
from typing import List, Optional

class CampaignStrategySchema(BaseModel):
    target_brand: str = Field(description="Main target brand name being analyzed")
    competitors: List[str] = Field(description="List of competitor brand names")
    category_theme: str = Field(description="General category theme or search topic")
    primary_search_term: str = Field(description="1-3 word primary term representing the brand or topic")
    strategic_reasoning: str = Field(description="Detailed explanation of the search strategy and deep thinking")
    search_queries: List[str] = Field(description="3 to 6 targeted YouTube search query strings")
    search_modifiers: List[str] = Field(description="Search modifier keywords like review, opiniao, comparativo")
    exclude_keywords: List[str] = Field(description="Negative keywords to filter out unwanted noise")
    recommended_region: str = Field(default="BR", description="2-letter ISO region code")
    recommended_video_type: str = Field(default="both", description="videos, shorts, or both")
    recommended_sort_by: str = Field(default="relevance", description="relevance, viewCount, or date")
    recommended_channels: List[str] = Field(default_factory=list, description="Optional channel names")
    additional_context_for_analysis: str = Field(description="Synthesized background context for downstream analysis")

class BriefingPlanner:
    """
    Leverages Gemini deep thinking to translate high-level campaign briefings
    or brand research objectives into optimized YouTube search strategies.
    """
    def __init__(self, config_path=None):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if config_path is None:
            config_path = os.path.join(self.project_root, 'config.ini')
        
        self.config_path = config_path
        self._load_configuration()
        self.client = create_genai_client(config_path=self.config_path)

    def _load_configuration(self):
        config = configparser.ConfigParser(interpolation=None)
        if os.path.exists(self.config_path):
            config.read(self.config_path)
            
        self.pro_model_name = config.get('Analysis', 'pro_model_name', fallback='gemini-flash-latest')
        self.flash_model_name = config.get('Analysis', 'flash_model_name', fallback='gemini-flash-latest')
        self.fallback_model_name = config.get('Analysis', 'fallback_model_name', fallback='gemini-3.6-flash')
        
        prompt_rel_path = config.get('Analysis', 'briefing_prompt_template_path', fallback='templates/prompts/briefing_planner.txt')
        self.prompt_path = os.path.join(self.project_root, prompt_rel_path)

    def plan_campaign(self, campaign_briefing, output_language="Portuguese", region_code="BR", additional_context="", enable_google_search=True):
        """
        Takes a campaign briefing and returns a structured search strategy for YouTube API.
        """
        if not campaign_briefing or not campaign_briefing.strip():
            raise ValueError("Campaign briefing cannot be empty.")

        if os.path.exists(self.prompt_path):
            with open(self.prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        else:
            prompt_template = """
You are a Senior Digital Marketing Strategist and YouTube Search API Expert.
Analyze the following Campaign Briefing and generate an optimized YouTube search strategy.

## CAMPAIGN BRIEFING:
{{CAMPAIGN_BRIEFING}}

## CONTEXT:
Language: {{OUTPUT_LANGUAGE}}
Region: {{REGION_CODE}}
Additional Context: {{ADDITIONAL_CONTEXT}}
"""

        prompt = prompt_template.replace("{{CAMPAIGN_BRIEFING}}", campaign_briefing.strip())
        prompt = prompt.replace("{{OUTPUT_LANGUAGE}}", output_language)
        prompt = prompt.replace("{{REGION_CODE}}", region_code)
        prompt = prompt.replace("{{ADDITIONAL_CONTEXT}}", additional_context or "None provided")

        print(f"\n🧠 Initiating Gemini Deep Thinking for Campaign Briefing...")
        print(f"Primary Model: {self.pro_model_name}")

        response_text = self._call_gemini_json(prompt, self.pro_model_name, self.fallback_model_name, enable_google_search=enable_google_search)
        
        if not response_text:
            raise RuntimeError("Failed to get search strategy from Gemini API.")

        strategy = self._parse_json_response(response_text)
        return strategy

    def _call_gemini_json(self, prompt, model_name, fallback_model_name=None, enable_google_search=True):
        kwargs = {
            "response_mime_type": "application/json",
            "response_schema": CampaignStrategySchema
        }
        if enable_google_search:
            kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
            
        config = types.GenerateContentConfig(**kwargs)
        
        try:
            response = generate_content_with_retry(
                client=self.client,
                model=model_name,
                contents=prompt,
                config=config,
                fallback_model=fallback_model_name or self.fallback_model_name
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Error calling Gemini in briefing planner: {e}")

        return None

    def _parse_json_response(self, text):
        """Parse structured strategy response using Pydantic schema."""
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            return CampaignStrategySchema.model_validate_json(cleaned).model_dump()
        except Exception:
            return json.loads(cleaned)
