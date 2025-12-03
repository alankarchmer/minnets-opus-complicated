from typing import Optional
import asyncio

from models import Memory, SearchResult, Suggestion, SuggestionSource
from retrieval.supermemory import SupermemoryClient
from retrieval.exa_search import ExaSearchClient
from retrieval.scoring import RetrievalScorer
from config import get_settings


class GraphPivotRetriever:
    """
    Implements the "Graph Pivot" retrieval strategy.
    
    The key insight: Don't show the user what matches their screen.
    Find the Anchor (direct match), then pivot to its graph neighbors.
    
    Strategy:
    1. Extract key concepts from context
    2. Find Anchors via vector search (high similarity)
    3. Filter out Echo Chamber (similarity > 0.85)
    4. Graph Pivot: Get neighbors via relationships (derives, extends, contrast)
    5. Apply MMR Doughnut Scoring
    6. Apply Temporal Novelty Boost
    7. Optionally enrich with web search
    """
    
    def __init__(self):
        self.supermemory = SupermemoryClient()
        self.exa = ExaSearchClient()
        self.scorer = RetrievalScorer()
        self.settings = get_settings()
    
    async def retrieve(
        self,
        context: str,
        concepts: list[str],
        include_web_search: bool = False
    ) -> list[tuple[Memory | SearchResult, float, float, float]]:
        """
        Main retrieval pipeline using Graph Pivot strategy.
        
        Args:
            context: The full screen context
            concepts: Extracted key concepts
            include_web_search: Whether to also search the web
            
        Returns:
            List of (item, score, relevance_score, novelty_score) tuples
        """
        # Combine concepts into search query
        search_query = " ".join(concepts[:5])  # Limit to top 5 concepts
        
        # Step 1: Find Anchors via Supermemory semantic search
        anchors = await self.supermemory.search(
            search_query, 
            limit=self.settings.max_anchors
        )
        
        if not anchors:
            # No anchors found - fall back to web search only
            if include_web_search:
                web_results = await self.exa.search(search_query, num_results=5)
                return self.scorer.filter_and_rank(web_results, self.settings.max_suggestions)
            return []
        
        # Step 2: Filter out Echo Chamber (similarity > 0.85)
        # These are TOO similar to what's on screen - not useful
        valid_anchors = [
            a for a in anchors 
            if a.similarity < self.settings.max_similarity_threshold
        ]
        
        # Step 3: Graph Pivot - Get neighbors via relationships
        neighbors: list[Memory] = []
        
        # Also keep anchors that are in sweet spot
        sweet_spot_anchors = [
            a for a in anchors 
            if self.settings.min_similarity_threshold <= a.similarity < self.settings.max_similarity_threshold
        ]
        
        # Get graph neighbors for high-similarity anchors (the pivot)
        high_sim_anchors = [a for a in anchors if a.similarity >= self.settings.max_similarity_threshold]
        
        if high_sim_anchors:
            # These are echo chamber - pivot to their neighbors
            neighbor_tasks = [
                self.supermemory.get_related(
                    anchor.id,
                    relationship_types=["derives", "extends", "contrast"]
                )
                for anchor in high_sim_anchors[:3]  # Limit to top 3 anchors
            ]
            
            neighbor_results = await asyncio.gather(*neighbor_tasks)
            for result in neighbor_results:
                neighbors.extend(result)
        
        # Combine: sweet spot anchors + graph neighbors
        all_candidates = sweet_spot_anchors + neighbors
        
        # Remove duplicates by ID
        seen_ids = set()
        unique_candidates = []
        for candidate in all_candidates:
            if candidate.id not in seen_ids:
                seen_ids.add(candidate.id)
                unique_candidates.append(candidate)
        
        # Step 4: Apply scoring
        scored_memories = self.scorer.filter_and_rank(
            unique_candidates, 
            self.settings.max_suggestions
        )
        
        # Step 5: Optionally add web search results
        if include_web_search:
            web_results = await self.exa.search(search_query, num_results=3)
            scored_web = self.scorer.filter_and_rank(web_results, 2)
            
            # Interleave memory and web results
            all_scored = scored_memories + scored_web
            all_scored.sort(key=lambda x: x[1], reverse=True)
            return all_scored[:self.settings.max_suggestions]
        
        return scored_memories
    
    async def close(self):
        """Clean up resources."""
        await self.supermemory.close()

