import math
from datetime import datetime, timezone
from typing import Union

from models import Memory, SearchResult


class RetrievalScorer:
    """
    Implements the "Doughnut" MMR scoring model and temporal novelty boost.
    
    The Doughnut Model:
    - The Hole (> 0.85): Echo chamber - content too similar to screen context. Penalize.
    - The Doughnut (0.65 - 0.85): Sweet spot - semantic overlap but distinct content. Bonus.
    - The Air (< 0.65): Too distant, likely irrelevant. Drop.
    
    Temporal Novelty:
    - Older memories get boosted (forgotten = more valuable to resurface)
    - Score_final = Score_vector × (1 + log(DaysSinceLastRead))
    """
    
    def __init__(
        self,
        min_similarity: float = 0.65,
        max_similarity: float = 0.85,
        echo_penalty: float = 0.5,
        sweet_spot_bonus: float = 1.2
    ):
        self.min_similarity = min_similarity
        self.max_similarity = max_similarity
        self.echo_penalty = echo_penalty
        self.sweet_spot_bonus = sweet_spot_bonus
    
    def apply_mmr_scoring(
        self, 
        items: list[Union[Memory, SearchResult]], 
        context_similarity: float = None
    ) -> list[tuple[Union[Memory, SearchResult], float, float, float]]:
        """
        Apply MMR Doughnut scoring to a list of items.
        
        Returns list of tuples: (item, final_score, relevance_score, novelty_score)
        """
        scored_items = []
        
        for i, item in enumerate(items):
            # Get similarity score
            if isinstance(item, Memory):
                sim = item.similarity
            else:
                # For web results, use position-based scoring
                # First result is most relevant, decrease from there
                # Put them in the "sweet spot" range (0.65-0.85)
                sim = 0.85 - (i * 0.05)  # 0.85, 0.80, 0.75, 0.70, 0.65
                sim = max(0.65, sim)
            
            # Apply doughnut scoring
            if sim > self.max_similarity:
                # Echo chamber - penalize heavily
                relevance_score = sim * self.echo_penalty
                novelty_score = 0.2  # Low novelty
            elif self.min_similarity <= sim <= self.max_similarity:
                # Sweet spot - bonus
                relevance_score = sim * self.sweet_spot_bonus
                # Novelty is inverse of similarity in sweet spot
                novelty_score = 1.0 - (sim - self.min_similarity) / (self.max_similarity - self.min_similarity)
                novelty_score = max(0.5, min(1.0, novelty_score))  # Clamp between 0.5-1.0
            else:
                # Too distant - still include but lower score
                relevance_score = sim * 0.8
                novelty_score = 0.8  # High novelty since it's distant
            
            # Normalize relevance to 0-1 range
            relevance_score = min(1.0, relevance_score)
            
            # Always include web results (don't filter by zero score)
            scored_items.append((item, relevance_score, relevance_score, novelty_score))
        
        return scored_items
    
    def apply_temporal_boost(
        self, 
        scored_items: list[tuple[Memory, float, float, float]]
    ) -> list[tuple[Memory, float, float, float]]:
        """
        Apply temporal novelty boost based on how long ago the memory was accessed.
        
        Formula: Score_final = Score × (1 + log(max(DaysSinceLastRead, 1)))
        
        Returns items with boosted scores.
        """
        now = datetime.now(timezone.utc)
        boosted_items = []
        
        for item, score, relevance, novelty in scored_items:
            if isinstance(item, Memory) and item.last_accessed:
                days_since = (now - item.last_accessed).days
                temporal_multiplier = 1 + math.log(max(days_since, 1))
                
                # Boost the novelty score based on age
                boosted_novelty = min(1.0, novelty * (1 + math.log(max(days_since, 1)) / 10))
                
                # Combined score
                boosted_score = score * temporal_multiplier
                boosted_items.append((item, boosted_score, relevance, boosted_novelty))
            else:
                # Web results don't get temporal boost
                boosted_items.append((item, score, relevance, novelty))
        
        return boosted_items
    
    def filter_and_rank(
        self,
        items: list[Union[Memory, SearchResult]],
        max_results: int = 3
    ) -> list[tuple[Union[Memory, SearchResult], float, float, float]]:
        """
        Full scoring pipeline: MMR + temporal boost + ranking.
        
        Returns top results sorted by score.
        """
        # Apply MMR scoring
        scored = self.apply_mmr_scoring(items)
        
        # Apply temporal boost for memories
        boosted = self.apply_temporal_boost(scored)
        
        # Filter out zero scores and sort by final score
        valid_items = [(item, score, rel, nov) for item, score, rel, nov in boosted if score > 0]
        sorted_items = sorted(valid_items, key=lambda x: x[1], reverse=True)
        
        return sorted_items[:max_results]

