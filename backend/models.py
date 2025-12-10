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
    ORTHOGONAL = "orthogonal"  # Cross-domain serendipitous discovery


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
    retrieval_path: Optional[str] = None  # graph, vector, web, graph_plus_web, vector_plus_web
    confidence: Optional[str] = None  # high, medium, low
    graph_insight: bool = False  # True if graph relationships were found
    should_offer_web: bool = False  # True if UI should show "Search Web" button


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


class VibeProfile(BaseModel):
    """
    Abstract emotional/aesthetic profile extracted from content.
    Used for cross-domain serendipitous matching.
    
    The key insight: Instead of matching content by topic similarity,
    match by the *type of person* who would appreciate it.
    """
    # Emotional signatures - how does this content "feel"?
    emotional_signatures: list[str] = Field(
        default_factory=list,
        description="Abstract feelings: melancholy, chaotic, intimate, precise, raw, playful, etc."
    )
    
    # Archetype description - who appreciates this?
    archetype: str = Field(
        default="",
        description="The type of person who values this: 'Someone who finds beauty in imperfection...'"
    )
    
    # Cross-domain suggestions - what else would this person love?
    cross_domain_interests: list[str] = Field(
        default_factory=list,
        description="Unrelated domains/things this archetype would appreciate"
    )
    
    # Anti-patterns - what this is NOT (helps with orthogonal projection)
    anti_patterns: list[str] = Field(
        default_factory=list,
        description="What this aesthetic rejects: 'polished', 'corporate', 'mass-produced'"
    )
    
    # Original domain for cross-domain search
    source_domain: str = Field(
        default="",
        description="The domain this vibe was extracted from: 'pottery', 'architecture', etc."
    )
