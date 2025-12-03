"""
Cascade Router: Graph → Vector → Web

Prioritizes insight over information:
1. Graph Check (High Value / Serendipity) - derives, extends relationships
2. Local Vector Check (Fast / Fact-Checking) - direct similarity
3. Web Search (New Information) - when local knowledge is insufficient
"""

import asyncio
from typing import Optional
from enum import Enum

from models import Memory, SearchResult, Suggestion, SuggestionSource
from retrieval.supermemory import SupermemoryClient
from retrieval.exa_search import ExaSearchClient
from retrieval.scoring import RetrievalScorer
from config import get_settings


class RetrievalPath(str, Enum):
    """Which retrieval path was used."""
    GRAPH = "graph"
    VECTOR = "vector"
    WEB = "web"
    GRAPH_PLUS_WEB = "graph_plus_web"
    VECTOR_PLUS_WEB = "vector_plus_web"


class ConfidenceLevel(str, Enum):
    """Confidence in the retrieval results."""
    HIGH = "high"      # > 0.85 - definitely in your notes
    MEDIUM = "medium"  # 0.65 - 0.85 - might be in your notes
    LOW = "low"        # < 0.65 - you don't know this


class CascadeResult:
    """Result from the cascade router."""
    def __init__(
        self,
        items: list,
        path: RetrievalPath,
        confidence: ConfidenceLevel,
        graph_insight: bool = False,
        should_offer_web: bool = False
    ):
        self.items = items
        self.path = path
        self.confidence = confidence
        self.graph_insight = graph_insight
        self.should_offer_web = should_offer_web


class CascadeRouter:
    """
    Implements the cascade architecture:
    
    Step 1: Graph Check - Look for derives/extends relationships
            If found → Bypass threshold, show immediately (highest value)
    
    Step 2: Vector Check - Direct similarity search
            High confidence (>0.85) → Show KB suggestion
            Medium (0.65-0.85) → Show KB + offer web search
            Low (<0.65) → Trigger web search
    
    Step 3: Web Search - When local knowledge is insufficient
    """
    
    def __init__(self):
        self.supermemory = SupermemoryClient()
        self.exa = ExaSearchClient()
        self.scorer = RetrievalScorer()
        self.settings = get_settings()
    
    async def route(
        self, 
        query: str, 
        context: str,
        force_web: bool = False
    ) -> CascadeResult:
        """
        Main routing logic. Returns results from the appropriate path.
        """
        
        # Step 1: Graph Check (Serendipity)
        graph_result = await self._check_graph(query)
        
        if graph_result:
            # Graph insight found - this is the highest value signal
            # Optionally supplement with web for even richer context
            if force_web:
                web_results = await self.exa.search(query, num_results=2)
                return CascadeResult(
                    items=graph_result + web_results,
                    path=RetrievalPath.GRAPH_PLUS_WEB,
                    confidence=ConfidenceLevel.HIGH,
                    graph_insight=True
                )
            
            return CascadeResult(
                items=graph_result,
                path=RetrievalPath.GRAPH,
                confidence=ConfidenceLevel.HIGH,
                graph_insight=True
            )
        
        # Step 2: Vector Check (Recall)
        vector_result, confidence = await self._check_vector(query)
        
        if confidence == ConfidenceLevel.HIGH:
            # Definitely in your notes
            return CascadeResult(
                items=vector_result,
                path=RetrievalPath.VECTOR,
                confidence=ConfidenceLevel.HIGH,
                graph_insight=False
            )
        
        elif confidence == ConfidenceLevel.MEDIUM:
            # Might be in your notes - offer web search button
            return CascadeResult(
                items=vector_result,
                path=RetrievalPath.VECTOR,
                confidence=ConfidenceLevel.MEDIUM,
                graph_insight=False,
                should_offer_web=True
            )
        
        # Step 3: Low confidence - trigger web search
        web_results = await self.exa.search(query, num_results=5)
        
        # Combine with any vector results we did find
        if vector_result:
            return CascadeResult(
                items=vector_result + web_results,
                path=RetrievalPath.VECTOR_PLUS_WEB,
                confidence=ConfidenceLevel.LOW,
                graph_insight=False
            )
        
        return CascadeResult(
            items=web_results,
            path=RetrievalPath.WEB,
            confidence=ConfidenceLevel.LOW,
            graph_insight=False
        )
    
    async def _check_graph(self, query: str) -> Optional[list[Memory]]:
        """
        Check for graph connections (derives, extends, updates).
        Returns memories if strong graph insight found.
        
        In Supermemory, relationships are:
        - extends: New info adds to existing knowledge
        - updates: New info contradicts/updates existing knowledge
        - derives: Inferred connections from patterns
        """
        # First, find anchors with include_related=True to get relationships
        anchors = await self.supermemory.search(query, limit=3, include_related=True)
        
        if not anchors:
            return None
        
        # Look for memories with graph relationships
        all_related = []
        
        for anchor in anchors:
            # Check if anchor has meaningful relationships already in context
            if anchor.relationships:
                # This anchor has graph connections - add it as an insight
                for rel in anchor.relationships:
                    rel_type = rel.get("type", "").replace("child_", "")
                    if rel_type in ["derives", "extends", "updates"]:
                        all_related.append(anchor)
                        break
            
            # Also search for related memories via the anchor
            related = await self.supermemory.get_related(
                anchor.id,
                relationship_types=["derives", "extends", "updates"]
            )
            all_related.extend(related)
        
        # Return if we found graph-connected insights
        if all_related:
            # Deduplicate and score
            seen_ids = set()
            unique = []
            for m in all_related:
                if m.id not in seen_ids:
                    seen_ids.add(m.id)
                    unique.append(m)
            
            # Apply scoring
            scored = self.scorer.filter_and_rank(unique, max_results=3)
            return [item for item, _, _, _ in scored]
        
        return None
    
    async def _check_vector(self, query: str) -> tuple[list[Memory], ConfidenceLevel]:
        """
        Direct vector similarity search.
        Returns memories and confidence level.
        """
        memories = await self.supermemory.search(query, limit=5)
        
        if not memories:
            return [], ConfidenceLevel.LOW
        
        # Calculate average similarity of top results
        top_similarities = [m.similarity for m in memories[:3]]
        avg_similarity = sum(top_similarities) / len(top_similarities)
        
        # Determine confidence level
        if avg_similarity > 0.85:
            confidence = ConfidenceLevel.HIGH
        elif avg_similarity >= 0.65:
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW
        
        # Apply scoring (including MMR doughnut)
        scored = self.scorer.filter_and_rank(memories, max_results=3)
        result = [item for item, _, _, _ in scored]
        
        return result, confidence
    
    async def trigger_web_search(self, query: str) -> list[SearchResult]:
        """
        Explicit web search trigger (for "Search Web" button).
        """
        return await self.exa.search(query, num_results=5)
    
    async def close(self):
        """Clean up resources."""
        await self.supermemory.close()

