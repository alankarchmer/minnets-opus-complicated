from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
from typing import Optional


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CamelModel(BaseModel):
    """Base model with camelCase serialization for Swift compatibility."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        json_encoders={datetime: lambda v: v.isoformat()}
    )


class SuggestionSource(str, Enum):
    SUPERMEMORY = "supermemory"
    WEB_SEARCH = "web_search"
    COMBINED = "combined"


class Suggestion(CamelModel):
    """A suggestion to show to the user."""
    id: str
    title: str
    content: str
    reasoning: str
    source: SuggestionSource
    relevance_score: float = Field(ge=0, le=1)
    novelty_score: float = Field(ge=0, le=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_url: Optional[str] = None


class AnalyzeRequest(CamelModel):
    """Request to analyze user context and get suggestions."""
    context: str
    app_name: str
    window_title: str


class AnalyzeResponse(CamelModel):
    """Response containing suggestions."""
    suggestions: list[Suggestion]
    processing_time_ms: int


class SaveToMemoryRequest(CamelModel):
    """Request to save a suggestion to Supermemory."""
    title: str
    content: str
    source_url: Optional[str] = None
    context: Optional[str] = None


class Memory(BaseModel):
    """A memory from Supermemory."""
    id: str
    content: str
    similarity: float
    created_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    source_document_id: Optional[str] = None
    relationships: list[dict] = Field(default_factory=list)


class SearchResult(BaseModel):
    """Search result from Exa.ai."""
    title: str
    url: str
    text: str
    score: float
    published_date: Optional[str] = None
