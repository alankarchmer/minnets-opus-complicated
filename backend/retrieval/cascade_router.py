"""
Cascade Router: Graph Pivot → Vector → Web

Combines the cascade architecture with the Graph Pivot strategy:

Graph Pivot (Step 1):
- Find anchors via vector search
- Echo chamber filter: similarity > 0.85 → pivot to neighbors instead
- Sweet spot: 0.65-0.85 similarity → keep these (related but novel)
- Pivot: Get graph neighbors (derives, extends, contrast) from echo chamber anchors

Cascade Fallback (Steps 2-3):
- Vector Check: Direct similarity with confidence levels
- Web Search: When local knowledge is insufficient
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
    Implements cascade architecture with Graph Pivot strategy.
    
    Step 1: Graph Pivot Check
            - Find anchors, filter echo chamber (>0.85 similarity)
            - Keep sweet spot anchors (0.65-0.85)
            - Pivot from echo chamber to graph neighbors
            - If insights found → Show immediately (highest value)
    
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
        Graph Pivot strategy: Don't show what matches the screen.
        Find anchors, filter echo chamber, pivot to graph neighbors.
        
        The key insight: High similarity (>0.85) = echo chamber = redundant.
        Instead, use those as pivot points to find connected but different content.
        
        Categories:
        - Echo Chamber (>0.85): Too similar - pivot to their neighbors
        - Sweet Spot (0.65-0.85): Related but novel - keep these
        - Too Distant (<0.65): Probably irrelevant - ignore
        
        Relationship types:
        - derives: Inferred connections from patterns
        - extends: New info adds to existing knowledge
        - contrast: Opposing or alternative viewpoints
        """
        # Find anchors with relationships
        anchors = await self.supermemory.search(
            query, 
            limit=self.settings.max_anchors,
            include_related=True
        )
        
        if not anchors:
            return None
        
        # Categorize anchors by similarity
        echo_chamber_anchors = [
            a for a in anchors 
            if a.similarity >= self.settings.max_similarity_threshold
        ]
        sweet_spot_anchors = [
            a for a in anchors 
            if self.settings.min_similarity_threshold <= a.similarity < self.settings.max_similarity_threshold
        ]
        
        # Graph Pivot: Get neighbors from echo chamber anchors
        # These are too similar to show directly, but their connections are valuable
        neighbors: list[Memory] = []
        
        if echo_chamber_anchors:
            # Pivot to graph neighbors for echo chamber items
            neighbor_tasks = [
                self.supermemory.get_related(
                    anchor.id,
                    relationship_types=["derives", "extends", "contrast"]
                )
                for anchor in echo_chamber_anchors[:3]  # Limit to top 3
            ]
            
            neighbor_results = await asyncio.gather(*neighbor_tasks)
            for result in neighbor_results:
                neighbors.extend(result)
        
        # Also check sweet spot anchors for graph relationships
        for anchor in sweet_spot_anchors:
            if anchor.relationships:
                # This anchor has graph connections - get related memories
                related = await self.supermemory.get_related(
                    anchor.id,
                    relationship_types=["derives", "extends", "contrast"]
                )
                neighbors.extend(related)
        
        # Combine: sweet spot anchors + graph neighbors (NOT echo chamber anchors)
        all_candidates = sweet_spot_anchors + neighbors
        
        if not all_candidates:
            return None
        
        # Deduplicate by ID
        seen_ids = set()
        unique_candidates = []
        for candidate in all_candidates:
            if candidate.id not in seen_ids:
                seen_ids.add(candidate.id)
                unique_candidates.append(candidate)
        
        if not unique_candidates:
            return None
        
        # Apply MMR doughnut scoring
        scored = self.scorer.filter_and_rank(
            unique_candidates, 
            max_results=self.settings.max_suggestions
        )
        
        return [item for item, _, _, _ in scored] if scored else None
    
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

