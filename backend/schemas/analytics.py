"""Pydantic schemas for Analytics."""
from typing import List
from pydantic import BaseModel, Field


class TopDomain(BaseModel):
    """Top domain schema for analytics."""
    domain: str
    clicks: int
    ctr: float = Field(..., description="Click-through rate as percentage")


class AnalyticsSummary(BaseModel):
    """Analytics summary schema."""
    period: str = Field(..., description="Time period: '7d' or '30d'")
    total_clicks: int
    total_impressions: int = 0
    ctr: float = Field(0.0, description="Overall click-through rate as percentage")
    total_previews: int
    total_domains: int
    verified_domains: int = 0
    brand_score: int = Field(..., ge=0, le=100, description="Brand score (0-100)")
    top_domains: List[TopDomain]
    
    class Config:
        json_schema_extra = {
            "example": {
                "period": "7d",
                "total_clicks": 2816,
                "total_previews": 6,
                "total_domains": 4,
                "brand_score": 94,
                "top_domains": [
                    {"domain": "example.com", "clicks": 1234, "ctr": 12.5},
                    {"domain": "mysite.io", "clicks": 892, "ctr": 10.2},
                ],
            }
        }

