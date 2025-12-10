"""
Cascade Router: Orthogonal → Graph Pivot → Vector → Web

Combines the cascade architecture with Orthogonal Search and Graph Pivot strategy:

Orthogonal Search (Step 0 - Serendipity):
- Extract "vibe" of content (emotional signatures, archetype)
- Search via noise injection (adjacent semantic clusters)
- Search via archetype bridging (what same type of person loves elsewhere)
- Search via cross-domain projection (vibe in different categories)

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
from typing import Optional, Union
from enum import Enum

from models import Memory, SearchResult, VibeProfile, StrategyWeights
from retrieval.supermemory import SupermemoryClient
from retrieval.exa_search import ExaSearchClient
from retrieval.scoring import RetrievalScorer
from retrieval.orthogonal_search import OrthogonalSearcher, OrthogonalResult
from synthesis.openai_client import OpenAISynthesizer
from config import get_settings


class ScoredCandidate:
    """
    Wrapper for retrieval candidates with provenance tracking.
    Tracks source (web/local) and strategy (orthogonal/vector) for weighted ranking.
    """
    def __init__(
        self,
        item: Union[Memory, SearchResult],
        source: str,  # "web" or "supermemory"
        strategy: str,  # "orthogonal", "vector", "graph"
        raw_score: float = 0.0
    ):
        self.item = item
        self.source = source
        self.strategy = strategy
        self.raw_score = raw_score
        self.adjusted_score = raw_score
    
    def apply_weight_boost(self, weights: StrategyWeights):
        """Apply weight-based boosting to the score."""
        score = self.raw_score
        
        # Boost by SOURCE match
        if self.source == "web":
            score *= (1 + weights.source_web)
        elif self.source == "supermemory":
            score *= (1 + weights.source_local)
        
        # Boost by INTENT match
        if self.strategy == "orthogonal":
            # If user wants serendipity, boost these items heavily
            score *= (1 + weights.serendipity * 2.0)
        else:
            # Vector/graph results get relevance boost
            score *= (1 + weights.relevance)
        
        self.adjusted_score = score
        return self


class RetrievalPath(str, Enum):
    """Which retrieval path was used."""
    ORTHOGONAL = "orthogonal"  # Serendipitous cross-domain discovery
    ORTHOGONAL_PLUS_GRAPH = "orthogonal_plus_graph"
    GRAPH = "graph"
    VECTOR = "vector"
    WEB = "web"
    GRAPH_PLUS_WEB = "graph_plus_web"
    VECTOR_PLUS_WEB = "vector_plus_web"
    WEIGHTED = "weighted"  # Dynamic multi-strategy based on StrategyWeights
    # Vector math strategies (true embedding arithmetic)
    VECTOR_MATH = "vector_math"  # PCA, antonym, bridge combined
    VECTOR_MATH_PCA = "vector_math_pca"  # Principal component subtraction only
    VECTOR_MATH_ANTONYM = "vector_math_antonym"  # Antonym steering only
    VECTOR_MATH_BRIDGE = "vector_math_bridge"  # Cross-modal bridge only


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
        should_offer_web: bool = False,
        orthogonal_metadata: dict = None,
        vibe_profile: VibeProfile = None
    ):
        self.items = items
        self.path = path
        self.confidence = confidence
        self.graph_insight = graph_insight
        self.should_offer_web = should_offer_web
        # Orthogonal search metadata (strategies used, queries, etc.)
        self.orthogonal_metadata = orthogonal_metadata or {}
        # Extracted vibe profile for provenance transparency
        self.vibe_profile = vibe_profile


class CascadeRouter:
    """
    Implements cascade architecture with Orthogonal Search and Graph Pivot strategy.
    
    Step 0: Orthogonal Search (Serendipity)
            - Extract vibe (emotional signatures, archetype)
            - Noise injection: perturb query to adjacent clusters
            - Archetype bridge: find what same person type loves elsewhere
            - Cross-domain: project vibe into different categories
    
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
    
    def __init__(self, synthesizer: OpenAISynthesizer = None):
        self.supermemory = SupermemoryClient()
        self.exa = ExaSearchClient()
        self.scorer = RetrievalScorer()
        self.settings = get_settings()
        self.synthesizer = synthesizer or OpenAISynthesizer()
        self.orthogonal = OrthogonalSearcher(
            exa_client=self.exa,
            synthesizer=self.synthesizer
        )
    
    async def route(
        self, 
        query: str, 
        context: str,
        force_web: bool = False,
        enable_orthogonal: bool = False
    ) -> CascadeResult:
        """
        Main routing logic. Returns results from the appropriate path.
        
        Args:
            query: Search query (usually tangential concepts)
            context: Full screen context
            force_web: Force web search even if KB has results
            enable_orthogonal: Enable orthogonal/serendipitous search
        """
        
        # Step 0: Orthogonal Search (Serendipity) - if enabled
        if enable_orthogonal:
            orthogonal_result = await self._check_orthogonal(context, query)
            if orthogonal_result and orthogonal_result.items:
                # Orthogonal search found serendipitous results
                # Optionally combine with graph results for richer context
                graph_result = await self._check_graph(query)
                
                if graph_result:
                    # Combine orthogonal + graph for maximum serendipity
                    combined = orthogonal_result.items[:2] + graph_result[:2]
                    return CascadeResult(
                        items=combined,
                        path=RetrievalPath.ORTHOGONAL_PLUS_GRAPH,
                        confidence=ConfidenceLevel.HIGH,
                        graph_insight=True,
                        orthogonal_metadata=orthogonal_result.metadata,
                        vibe_profile=orthogonal_result.vibe
                    )
                
                return CascadeResult(
                    items=orthogonal_result.items,
                    path=RetrievalPath.ORTHOGONAL,
                    confidence=ConfidenceLevel.MEDIUM,  # Orthogonal is inherently exploratory
                    graph_insight=False,
                    orthogonal_metadata=orthogonal_result.metadata,
                    vibe_profile=orthogonal_result.vibe
                )
        
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
    
    async def route_weighted(
        self,
        query: str,
        context: str,
        weights: StrategyWeights
    ) -> CascadeResult:
        """
        Route using allocation-based multi-strategy execution.
        
        Key principle: Weights determine HOW MANY results to fetch and 
        HOW MUCH to boost scores, not binary on/off switches.
        
        Args:
            query: Search query (usually tangential concepts)
            context: Full screen context (passed to orthogonal for antonym steering)
            weights: LLM-determined strategy weights
            
        Returns:
            CascadeResult with items from multiple strategies, ranked by adjusted score
        """
        tasks = []
        task_metadata = []  # Track (source, strategy) for each task
        
        # --- 1. BUDGET ALLOCATION ---
        # Total fetch pool before ranking
        base_fetch_count = 10
        
        # Calculate dynamic limits (minimum 1 if weight > 0.1 to avoid total silence)
        limit_web = max(1, int(base_fetch_count * weights.source_web)) if weights.source_web > 0.1 else 0
        limit_local = max(1, int(base_fetch_count * weights.source_local)) if weights.source_local > 0.1 else 0
        
        print(f"   📊 Budget allocation: web={limit_web}, local={limit_local}")
        print(f"      Weights: serendipity={weights.serendipity:.2f}, relevance={weights.relevance:.2f}")
        
        # --- 2. DISPATCH STRATEGIES ---
        
        # Track A: Serendipity (Orthogonal Search)
        # Low threshold (0.2) - even a little serendipity desire gets some results
        if weights.serendipity > 0.2:
            # Scale lambda_surprise based on the weight
            # Higher serendipity = more aggressive orthogonal search
            lambda_surprise = weights.serendipity * 1.5
            
            tasks.append(self._fetch_orthogonal(
                query=query,
                context=context,
                lambda_surprise=lambda_surprise,
                limit=min(3, limit_web + limit_local)  # Orthogonal draws from both
            ))
            task_metadata.append(("mixed", "orthogonal"))
        
        # Track B: Relevance (Standard Vector Search from Supermemory)
        if limit_local > 0:
            tasks.append(self._fetch_local(query, limit=limit_local))
            task_metadata.append(("supermemory", "vector"))
        
        # Track C: Web (Exa search)
        if limit_web > 0:
            tasks.append(self._fetch_web(query, limit=limit_web))
            task_metadata.append(("web", "vector"))
        
        # --- 3. EXECUTE PARALLEL ---
        if not tasks:
            print("   ⚠️ No strategies dispatched (all weights too low)")
            return CascadeResult(
                items=[],
                path=RetrievalPath.WEIGHTED,
                confidence=ConfidenceLevel.LOW
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # --- 4. COLLECT & TAG CANDIDATES ---
        candidates: list[ScoredCandidate] = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"   ⚠️ Strategy {task_metadata[i]} failed: {result}")
                continue
            
            source, strategy = task_metadata[i]
            
            for item in result:
                # Get raw score
                if isinstance(item, Memory):
                    raw_score = item.similarity
                elif isinstance(item, SearchResult):
                    raw_score = item.score
                else:
                    raw_score = 0.5  # Default
                
                candidate = ScoredCandidate(
                    item=item,
                    source=source if source != "mixed" else ("web" if isinstance(item, SearchResult) else "supermemory"),
                    strategy=strategy,
                    raw_score=raw_score
                )
                candidates.append(candidate)
        
        if not candidates:
            print("   ⚠️ No candidates from any strategy")
            return CascadeResult(
                items=[],
                path=RetrievalPath.WEIGHTED,
                confidence=ConfidenceLevel.LOW
            )
        
        # --- 5. WEIGHTED RANKING (the secret sauce) ---
        # Apply weight-based boosting
        for candidate in candidates:
            candidate.apply_weight_boost(weights)
        
        # Sort by adjusted score
        candidates.sort(key=lambda x: x.adjusted_score, reverse=True)
        
        # Deduplicate by content (keep highest scored version)
        seen_content = set()
        unique_candidates = []
        for candidate in candidates:
            # Create content fingerprint
            if isinstance(candidate.item, Memory):
                content_key = candidate.item.content[:100]
            else:
                content_key = candidate.item.url
            
            if content_key not in seen_content:
                seen_content.add(content_key)
                unique_candidates.append(candidate)
        
        # Take top N
        top_candidates = unique_candidates[:self.settings.max_suggestions]
        
        # Calculate confidence based on top scores
        if top_candidates:
            avg_adjusted = sum(c.adjusted_score for c in top_candidates) / len(top_candidates)
            if avg_adjusted > 1.5:
                confidence = ConfidenceLevel.HIGH
            elif avg_adjusted > 1.0:
                confidence = ConfidenceLevel.MEDIUM
            else:
                confidence = ConfidenceLevel.LOW
        else:
            confidence = ConfidenceLevel.LOW
        
        # Log strategy distribution
        strategies_used = {}
        for c in top_candidates:
            key = f"{c.source}:{c.strategy}"
            strategies_used[key] = strategies_used.get(key, 0) + 1
        print(f"   ✅ Weighted routing: {len(top_candidates)} results from {strategies_used}")
        
        return CascadeResult(
            items=[c.item for c in top_candidates],
            path=RetrievalPath.WEIGHTED,
            confidence=confidence,
            orthogonal_metadata={
                "weights": weights.model_dump(),
                "strategies_used": strategies_used,
                "total_candidates": len(candidates)
            }
        )
    
    async def _fetch_orthogonal(
        self,
        query: str,
        context: str,
        lambda_surprise: float,
        limit: int,
        include_vector_math: bool = True
    ) -> list[SearchResult]:
        """
        Fetch results using orthogonal search strategies.
        
        Args:
            query: Search query
            context: Screen context
            lambda_surprise: Serendipity intensity
            limit: Max results to return
            include_vector_math: Whether to include vector math strategies (PCA, antonym, bridge)
        """
        try:
            # Optionally fetch user memories for vector math strategies
            user_memories = None
            if include_vector_math:
                user_memories = await self.supermemory.search("", limit=20)
            
            results = await self.orthogonal.search_all_strategies(
                context=context,
                original_query=query,
                num_results_per_strategy=max(1, limit // 3),
                include_vector_math=include_vector_math and user_memories is not None,
                user_memories=user_memories
            )
            
            if not results:
                return []
            
            # Combine and take top results
            combined, _ = self.orthogonal.combine_results(results, max_total=limit)
            return combined
            
        except Exception as e:
            print(f"   ⚠️ Orthogonal fetch error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _fetch_local(self, query: str, limit: int) -> list[Memory]:
        """Fetch results from Supermemory (local knowledge base)."""
        try:
            memories = await self.supermemory.search(query, limit=limit)
            return memories or []
        except Exception as e:
            print(f"   ⚠️ Local fetch error: {e}")
            return []
    
    async def _fetch_web(self, query: str, limit: int) -> list[SearchResult]:
        """Fetch results from Exa (web search)."""
        try:
            results = await self.exa.search(query, num_results=limit)
            return results or []
        except Exception as e:
            print(f"   ⚠️ Web fetch error: {e}")
            return []

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
    
    async def _check_orthogonal(
        self, 
        context: str, 
        query: str
    ) -> Optional['OrthogonalCombinedResult']:
        """
        Orthogonal Search: Find serendipitous cross-domain results.
        
        Uses three strategies:
        1. Noise injection - perturb query embedding
        2. Archetype bridge - find what same person type loves
        3. Cross-domain - project vibe into different categories
        """
        try:
            # Run all orthogonal strategies
            results = await self.orthogonal.search_all_strategies(
                context=context,
                original_query=query,
                num_results_per_strategy=2
            )
            
            if not results:
                return None
            
            # Combine results from all strategies
            combined, metadata = self.orthogonal.combine_results(
                results,
                max_total=self.settings.max_suggestions + 1  # Get one extra for diversity
            )
            
            if not combined:
                return None
            
            # Extract vibe profile from results (if available)
            vibe = None
            for r in results:
                if r.vibe_profile and r.vibe_profile.archetype:
                    vibe = r.vibe_profile
                    break
            
            print(f"   🎲 Orthogonal search found {len(combined)} results")
            print(f"      Strategies: {metadata.get('strategies_used', [])}")
            
            return OrthogonalCombinedResult(
                items=combined,
                metadata=metadata,
                vibe=vibe
            )
            
        except Exception as e:
            print(f"   ⚠️ Orthogonal search error: {e}")
            return None
    
    async def route_orthogonal_only(
        self,
        context: str,
        query: str
    ) -> CascadeResult:
        """
        Route using ONLY orthogonal search strategies.
        Useful for testing and when maximum serendipity is desired.
        """
        result = await self._check_orthogonal(context, query)
        
        if result and result.items:
            return CascadeResult(
                items=result.items,
                path=RetrievalPath.ORTHOGONAL,
                confidence=ConfidenceLevel.MEDIUM,
                orthogonal_metadata=result.metadata,
                vibe_profile=result.vibe
            )
        
        # Fallback to standard web search if orthogonal fails
        web_results = await self.exa.search(query, num_results=5)
        return CascadeResult(
            items=web_results,
            path=RetrievalPath.WEB,
            confidence=ConfidenceLevel.LOW
        )
    
    # =========================================================================
    # VECTOR MATH ROUTING (True Embedding Arithmetic)
    # =========================================================================
    
    async def route_vector_math(
        self,
        context: str,
        query: str,
        user_memories: list[Memory] = None
    ) -> CascadeResult:
        """
        Route using ONLY vector math strategies (PCA, antonym, bridge).
        
        This is the mathematically pure serendipity path:
        - PCA: Subtract dominant taste to reveal hidden preferences
        - Antonym: Steer away from context, towards target vibe
        - Bridge: Transform content across domains
        
        Args:
            context: User's screen context
            query: Search query (used for fallback)
            user_memories: User's saved memories (fetched from Supermemory if not provided)
            
        Returns:
            CascadeResult with mathematically serendipitous items
        """
        # Fetch user memories if not provided
        if user_memories is None:
            user_memories = await self.supermemory.search("", limit=20)
        
        if not user_memories:
            print("   ⚠️ Vector math: No user memories available")
            # Fallback to standard web search
            web_results = await self.exa.search(query, num_results=5)
            return CascadeResult(
                items=web_results,
                path=RetrievalPath.WEB,
                confidence=ConfidenceLevel.LOW
            )
        
        try:
            # Run all vector math strategies
            results = await self.orthogonal.search_vector_math_only(
                context=context,
                user_memories=user_memories,
                num_results_per_strategy=3
            )
            
            if not results:
                print("   ⚠️ Vector math: No results from any strategy")
                web_results = await self.exa.search(query, num_results=5)
                return CascadeResult(
                    items=web_results,
                    path=RetrievalPath.WEB,
                    confidence=ConfidenceLevel.LOW
                )
            
            # Combine results from all strategies
            combined, metadata = self.orthogonal.combine_results(
                results,
                max_total=self.settings.max_suggestions + 1
            )
            
            # Build rich metadata
            orthogonal_metadata = {
                "strategies_used": metadata.get("strategies_used", []),
                "queries_used": metadata.get("queries_used", []),
                "subtracted_tags": [],
                "target_vibes": []
            }
            
            # Extract provenance info
            vibe = None
            for r in results:
                if r.vibe_profile and r.vibe_profile.archetype:
                    vibe = r.vibe_profile
                if r.subtracted_tags:
                    orthogonal_metadata["subtracted_tags"].extend(r.subtracted_tags)
                if r.target_vibe:
                    orthogonal_metadata["target_vibes"].append(r.target_vibe)
            
            print(f"   🧮 Vector math found {len(combined)} results")
            print(f"      Strategies: {orthogonal_metadata['strategies_used']}")
            
            return CascadeResult(
                items=combined,
                path=RetrievalPath.VECTOR_MATH,
                confidence=ConfidenceLevel.MEDIUM,  # Vector math is exploratory
                orthogonal_metadata=orthogonal_metadata,
                vibe_profile=vibe
            )
            
        except Exception as e:
            print(f"   ⚠️ Vector math routing error: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback to web search
            web_results = await self.exa.search(query, num_results=5)
            return CascadeResult(
                items=web_results,
                path=RetrievalPath.WEB,
                confidence=ConfidenceLevel.LOW
            )
    
    async def route_vector_math_pca(
        self,
        context: str,
        user_memories: list[Memory]
    ) -> CascadeResult:
        """
        Route using ONLY PCA subtraction strategy.
        
        Best for: Finding hidden preferences by removing dominant taste vectors.
        
        Args:
            context: User's screen context
            user_memories: User's saved memories
            
        Returns:
            CascadeResult with PCA-serendipitous items
        """
        if len(user_memories) < self.settings.pca_min_memories:
            return CascadeResult(
                items=[],
                path=RetrievalPath.VECTOR_MATH_PCA,
                confidence=ConfidenceLevel.LOW,
                orthogonal_metadata={"error": f"Need at least {self.settings.pca_min_memories} memories"}
            )
        
        vibe = await self.synthesizer.extract_vibe(context)
        
        result = await self.orthogonal.search_principal_component(
            user_memories=user_memories,
            vibe=vibe,
            num_results=self.settings.max_suggestions
        )
        
        return CascadeResult(
            items=result.items,
            path=RetrievalPath.VECTOR_MATH_PCA,
            confidence=ConfidenceLevel.MEDIUM if result.items else ConfidenceLevel.LOW,
            orthogonal_metadata={
                "strategy": "pca",
                "subtracted_tags": result.subtracted_tags,
                "query_used": result.query_used
            },
            vibe_profile=result.vibe_profile
        )
    
    async def route_vector_math_antonym(
        self,
        context: str,
        user_memories: list[Memory],
        target_vibe: str = None
    ) -> CascadeResult:
        """
        Route using ONLY antonym steering strategy.
        
        Best for: Escaping current context (e.g., sterile office → cozy cafe).
        
        Args:
            context: User's screen context
            user_memories: User's saved memories
            target_vibe: Optional specific target vibe to steer towards
            
        Returns:
            CascadeResult with contrast-steered items
        """
        vibe = await self.synthesizer.extract_vibe(context)
        
        result = await self.orthogonal.search_antonym_steering(
            current_context=context,
            user_memories=user_memories,
            vibe=vibe,
            target_vibe=target_vibe,
            num_results=self.settings.max_suggestions
        )
        
        return CascadeResult(
            items=result.items,
            path=RetrievalPath.VECTOR_MATH_ANTONYM,
            confidence=ConfidenceLevel.MEDIUM if result.items else ConfidenceLevel.LOW,
            orthogonal_metadata={
                "strategy": "antonym",
                "target_vibe": result.target_vibe,
                "query_used": result.query_used
            },
            vibe_profile=result.vibe_profile
        )
    
    async def route_vector_math_bridge(
        self,
        context: str,
        source_domain: str,
        target_domain: str
    ) -> CascadeResult:
        """
        Route using ONLY cross-modal bridge strategy.
        
        Best for: "If this movie were a restaurant, what would it be?"
        
        Args:
            context: User's screen context (content to transform)
            source_domain: Original domain (e.g., "movie")
            target_domain: Target domain (e.g., "restaurant")
            
        Returns:
            CascadeResult with cross-domain transformed items
        """
        vibe = await self.synthesizer.extract_vibe(context)
        
        result = await self.orthogonal.search_bridge_vector(
            content=context[:2000],
            source_domain=source_domain,
            target_domain=target_domain,
            vibe=vibe,
            num_results=self.settings.max_suggestions
        )
        
        return CascadeResult(
            items=result.items,
            path=RetrievalPath.VECTOR_MATH_BRIDGE,
            confidence=ConfidenceLevel.MEDIUM if result.items else ConfidenceLevel.LOW,
            orthogonal_metadata={
                "strategy": "bridge",
                "source_domain": source_domain,
                "target_domain": result.target_domain,
                "query_used": result.query_used
            },
            vibe_profile=result.vibe_profile
        )
    
    async def close(self):
        """Clean up resources."""
        await self.supermemory.close()


class OrthogonalCombinedResult:
    """Combined result from orthogonal search strategies."""
    def __init__(
        self,
        items: list[SearchResult],
        metadata: dict,
        vibe: Optional[VibeProfile] = None
    ):
        self.items = items
        self.metadata = metadata
        self.vibe = vibe

