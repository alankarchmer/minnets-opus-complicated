"""
Orthogonal Vector Search: Serendipitous Retrieval

This module implements six strategies for "tangential leaps" that go beyond
standard similarity-based retrieval:

LLM-Based Strategies (Original):
1. Vector Noise Injection - Perturb embeddings to land in adjacent semantic clusters
2. Archetype Bridge Search - Map user vibes → archetype → what else that archetype loves
3. Cross-Domain Vibe Search - Project emotional signatures into different categories

Vector Math Strategies (NEW - True Embedding Arithmetic):
4. Principal Component Subtraction - Remove dominant "genre" to reveal hidden "style"
5. Antonym Steering - Steer AWAY from current context, TOWARDS target vibe
6. Cross-Modal Bridge - Transform content from one domain to another

The key insight: Standard search finds content ABOUT the same topic.
Orthogonal search finds content that would delight the same TYPE OF PERSON.

Example:
- User reading about wabi-sabi pottery
- Standard search: "Japanese ceramics", "pottery techniques"  
- Orthogonal search: "Georgian restaurant with no website and handwritten menu"
  (same vibe: humble, authentic, discovered-not-advertised)
"""

import asyncio
import random
from typing import Optional
from dataclasses import dataclass, field

from models import VibeProfile, SearchResult, Memory
from retrieval.exa_search import ExaSearchClient
from retrieval.vector_math import OrthogonalVectorMath
from synthesis.openai_client import OpenAISynthesizer
from config import get_settings


@dataclass
class OrthogonalResult:
    """Result from orthogonal search with provenance information."""
    items: list[SearchResult]
    strategy: str  # "noise_injection", "archetype_bridge", "cross_domain", "pca", "antonym", "bridge"
    query_used: str
    vibe_profile: Optional[VibeProfile] = None
    target_domain: Optional[str] = None
    # Vector math provenance
    subtracted_tags: list[str] = field(default_factory=list)  # What was removed (for PCA)
    target_vibe: Optional[str] = None  # What we steered towards (for antonym)


class OrthogonalSearcher:
    """
    Implements six strategies for serendipitous "tangential leaps":
    
    LLM-Based (Original):
    1. Noise Injection: Add Gaussian noise to query embeddings to land in 
       adjacent semantic clusters. Like taking a random walk from your query.
       
    2. Archetype Bridge: Extract the "type of person" who appreciates the content,
       then search for what else that archetype would love in different domains.
       
    3. Cross-Domain Vibe: Take the emotional signatures from one domain and 
       project them into a completely different category.
    
    Vector Math (NEW - True Embedding Arithmetic):
    4. Principal Component Search: Remove dominant taste vectors via SVD to 
       reveal hidden style preferences. Q = V_user - λ * proj_Vdom(V_user)
       
    5. Antonym Steering: Steer away from current context towards a target vibe.
       Q = V_taste + α * (V_target - V_context)
       
    6. Bridge Vector Search: Transform content from one domain to another using
       pre-computed domain transformation vectors. Q = V_content + V_bridge
    """
    
    def __init__(self, exa_client: ExaSearchClient = None, synthesizer: OpenAISynthesizer = None):
        self.settings = get_settings()
        self.exa = exa_client or ExaSearchClient()
        self.synthesizer = synthesizer or OpenAISynthesizer()
        
        # Vector math engine for true embedding arithmetic
        self.vector_math = OrthogonalVectorMath(self.synthesizer)
        
        # Noise injection parameters
        self.noise_scale = self.settings.orthogonal_noise_scale
        
        # Target domains for cross-domain search
        self.target_domains = self.settings.orthogonal_target_domains
    
    async def search_with_noise(
        self, 
        query: str, 
        num_results: int = 5,
        noise_scale: float = None
    ) -> OrthogonalResult:
        """
        Vector Noise Injection: Perturb the query to land in adjacent semantic clusters.
        
        The math: Given query q, we search for q' = q + ε, where ε ~ N(0, σ²I)
        
        In practice, since we can't directly manipulate Exa's embeddings, we:
        1. Get the embedding of the original query
        2. Add Gaussian noise to the embedding
        3. Find the nearest "word" to the perturbed embedding (via nearest neighbor in our vocab)
        4. Use that as a modified query
        
        For simplicity, we use a linguistic approximation: add semantically adjacent
        words/concepts to the query that shift it slightly off its original direction.
        
        Args:
            query: Original search query
            num_results: Number of results to return
            noise_scale: Standard deviation for noise (default from config)
            
        Returns:
            OrthogonalResult with items and provenance
        """
        scale = noise_scale or self.noise_scale
        
        # Strategy: Generate "noisy" query variants by asking LLM to 
        # suggest semantically adjacent but different phrasings
        noisy_query = await self._generate_noisy_query(query, scale)
        
        print(f"   🎲 Noise-injected query: '{noisy_query}'")
        
        # Search with the noisy query
        results = await self.exa.search(
            query=noisy_query,
            num_results=num_results,
            use_autoprompt=True
        )
        
        return OrthogonalResult(
            items=results,
            strategy="noise_injection",
            query_used=noisy_query
        )
    
    async def search_via_archetype(
        self, 
        context: str,
        vibe: VibeProfile = None,
        target_domain: str = None,
        num_results: int = 5
    ) -> OrthogonalResult:
        """
        Archetype Bridge Search: Find content that would delight the same TYPE OF PERSON.
        
        The strategy:
        1. Extract the "vibe" of what the user is reading (if not provided)
        2. Identify the archetype - what type of person appreciates this?
        3. Pick a target domain different from the source
        4. Generate a query for that domain that captures the archetype's values
        5. Search for hidden gems in that new domain
        
        Args:
            context: The user's current screen context
            vibe: Pre-extracted VibeProfile (optional, will extract if not provided)
            target_domain: Specific domain to search in (optional, will pick randomly)
            num_results: Number of results to return
            
        Returns:
            OrthogonalResult with cross-domain items
        """
        # Extract vibe if not provided
        if vibe is None:
            vibe = await self.synthesizer.extract_vibe(context)
        
        if not vibe.archetype:
            # Fallback if vibe extraction failed
            return OrthogonalResult(
                items=[],
                strategy="archetype_bridge",
                query_used="",
                vibe_profile=vibe
            )
        
        # Pick a target domain different from the source
        if target_domain is None:
            available_domains = [
                d for d in self.target_domains 
                if d.lower() != vibe.source_domain.lower()
            ]
            target_domain = random.choice(available_domains) if available_domains else "experiences"
        
        # Generate a query that bridges the archetype to the new domain
        bridge_query = await self.synthesizer.generate_archetype_query(vibe, target_domain)
        
        # Search in the new domain
        results = await self.exa.search(
            query=bridge_query,
            num_results=num_results,
            use_autoprompt=True
        )
        
        return OrthogonalResult(
            items=results,
            strategy="archetype_bridge",
            query_used=bridge_query,
            vibe_profile=vibe,
            target_domain=target_domain
        )
    
    async def search_cross_domain(
        self, 
        vibe: VibeProfile,
        exclude_domains: list[str] = None,
        num_results: int = 5
    ) -> OrthogonalResult:
        """
        Cross-Domain Vibe Search: Project emotional signatures into a different category.
        
        Unlike archetype bridge (which generates a custom query), this directly
        uses the cross_domain_interests from the vibe profile as search queries.
        
        Args:
            vibe: Extracted VibeProfile with cross_domain_interests
            exclude_domains: Domains to exclude from search
            num_results: Number of results to return
            
        Returns:
            OrthogonalResult with items from different domains
        """
        if not vibe.cross_domain_interests:
            return OrthogonalResult(
                items=[],
                strategy="cross_domain",
                query_used="",
                vibe_profile=vibe
            )
        
        # Pick a random cross-domain interest to search for
        interest = random.choice(vibe.cross_domain_interests)
        
        print(f"   🌍 Cross-domain search: '{interest}'")
        
        # Search for this specific interest
        results = await self.exa.search(
            query=interest,
            num_results=num_results,
            use_autoprompt=True
        )
        
        return OrthogonalResult(
            items=results,
            strategy="cross_domain",
            query_used=interest,
            vibe_profile=vibe
        )
    
    # =========================================================================
    # VECTOR MATH STRATEGIES (True Embedding Arithmetic)
    # =========================================================================
    
    async def search_principal_component(
        self,
        user_memories: list[Memory],
        vibe: VibeProfile,
        num_results: int = 5
    ) -> OrthogonalResult:
        """
        Principal Component Subtraction: Remove dominant taste to reveal hidden preferences.
        
        Math: Q_serendipity = V_user - λ * proj_Vdom(V_user)
        
        The insight: If user loves "Cyberpunk Anime", "Cyberpunk Novels", 
        "Cyberpunk Games" - standard search sees "Cyberpunk" as dominant.
        By subtracting it, we reveal hidden preferences like "Neon Aesthetics".
        
        Strategy:
        1. Calculate serendipity vector via SVD subtraction
        2. Get "residual vibe" keywords from what remains
        3. Fetch broad results from Exa using flavored query
        4. Rerank by mathematical similarity to q_vector
        
        Args:
            user_memories: User's saved memories from Supermemory
            vibe: Extracted vibe profile for context
            num_results: Number of final results
            
        Returns:
            OrthogonalResult with mathematically serendipitous items
        """
        if len(user_memories) < self.settings.pca_min_memories:
            print(f"   ⚠️ PCA: Need at least {self.settings.pca_min_memories} memories, got {len(user_memories)}")
            return OrthogonalResult(
                items=[],
                strategy="pca",
                query_used="",
                vibe_profile=vibe
            )
        
        # 1. Calculate serendipity vector + get subtracted component names
        q_vector, subtracted_tags = await self.vector_math.principal_component_search(
            user_memories, 
            return_subtracted=True
        )
        
        print(f"   🧮 PCA subtracted: {subtracted_tags}")
        
        # 2. Translate vector -> guiding keywords for Exa
        guide_keywords = await self.synthesizer.describe_vector_vibe(vibe, subtracted_tags)
        
        # 3. Fetch BROAD results with flavored query
        broad_query = f"{guide_keywords} experience hidden gem"
        print(f"   🔍 PCA broad query: '{broad_query}'")
        
        raw_results = await self.exa.search(
            query=broad_query,
            num_results=self.settings.rerank_pool_size,
            use_autoprompt=True
        )
        
        if not raw_results:
            return OrthogonalResult(
                items=[],
                strategy="pca",
                query_used=broad_query,
                vibe_profile=vibe,
                subtracted_tags=subtracted_tags
            )
        
        # 4. Mathematical rerank by cosine similarity to q_vector
        reranked = await self.vector_math.rerank_by_vector(
            raw_results, 
            q_vector, 
            top_k=num_results
        )
        
        print(f"   ✨ PCA reranked {len(raw_results)} -> {len(reranked)} results")
        
        return OrthogonalResult(
            items=reranked,
            strategy="pca",
            query_used=broad_query,
            vibe_profile=vibe,
            subtracted_tags=subtracted_tags
        )
    
    async def search_antonym_steering(
        self,
        current_context: str,
        user_memories: list[Memory],
        vibe: VibeProfile,
        target_vibe: str = None,
        num_results: int = 5
    ) -> OrthogonalResult:
        """
        Antonym Steering: Steer AWAY from current context, TOWARDS target vibe.
        
        Math: Q = V_taste + α * (V_target_vibe - V_current_context)
        
        Unlike pure negation (-1 * V_context) which produces noise in high-dim space,
        this gives steering a DIRECTION. We move TOWARDS something (novelty, 
        relaxation) not just away from the current state.
        
        Example: User in sterile office → steer towards "cozy, chaotic, intimate"
        
        Args:
            current_context: User's current screen content
            user_memories: User's saved memories (for long-term taste)
            vibe: Extracted vibe profile
            target_vibe: Specific target vibe (optional, random if not provided)
            num_results: Number of final results
            
        Returns:
            OrthogonalResult with contrast-steered items
        """
        # 1. Calculate steering vector
        q_vector, used_target_vibe = await self.vector_math.antonym_steering_search(
            current_context,
            user_memories,
            target_vibe=target_vibe
        )
        
        print(f"   🧭 Antonym steering towards: '{used_target_vibe}'")
        
        # 2. Build a flavored query using the target vibe
        broad_query = f"{used_target_vibe} experience unique authentic"
        
        # 3. Fetch broad results
        raw_results = await self.exa.search(
            query=broad_query,
            num_results=self.settings.rerank_pool_size,
            use_autoprompt=True
        )
        
        if not raw_results:
            return OrthogonalResult(
                items=[],
                strategy="antonym",
                query_used=broad_query,
                vibe_profile=vibe,
                target_vibe=used_target_vibe
            )
        
        # 4. Mathematical rerank
        reranked = await self.vector_math.rerank_by_vector(
            raw_results,
            q_vector,
            top_k=num_results
        )
        
        print(f"   ✨ Antonym reranked {len(raw_results)} -> {len(reranked)} results")
        
        return OrthogonalResult(
            items=reranked,
            strategy="antonym",
            query_used=broad_query,
            vibe_profile=vibe,
            target_vibe=used_target_vibe
        )
    
    async def search_bridge_vector(
        self,
        content: str,
        source_domain: str,
        target_domain: str,
        vibe: VibeProfile,
        num_results: int = 5
    ) -> OrthogonalResult:
        """
        Cross-Modal Bridge: Transform content from one domain to another.
        
        Math: V_bridge = V_AvgDomain1 - V_AvgDomain2, then Q = V_content + V_bridge
        
        This is the "King - Man + Woman = Queen" analogy applied to domains.
        "If this movie were a restaurant, what would it be?"
        
        Args:
            content: Content to transform (e.g., movie description)
            source_domain: Original domain (e.g., "movie")
            target_domain: Target domain (e.g., "restaurant")
            vibe: Extracted vibe profile
            num_results: Number of final results
            
        Returns:
            OrthogonalResult with cross-domain transformed items
        """
        # 1. Calculate bridge-transformed vector
        q_vector = await self.vector_math.bridge_vector_search(
            content,
            source_domain,
            target_domain
        )
        
        print(f"   🌉 Bridge: {source_domain} -> {target_domain}")
        
        # 2. Build a flavored query for target domain
        # Use vibe signatures to flavor the query
        vibe_keywords = ", ".join(vibe.emotional_signatures[:3]) if vibe.emotional_signatures else "unique"
        broad_query = f"{target_domain} {vibe_keywords} hidden gem"
        
        # 3. Fetch broad results
        raw_results = await self.exa.search(
            query=broad_query,
            num_results=self.settings.rerank_pool_size,
            use_autoprompt=True
        )
        
        if not raw_results:
            return OrthogonalResult(
                items=[],
                strategy="bridge",
                query_used=broad_query,
                vibe_profile=vibe,
                target_domain=target_domain
            )
        
        # 4. Mathematical rerank
        reranked = await self.vector_math.rerank_by_vector(
            raw_results,
            q_vector,
            top_k=num_results
        )
        
        print(f"   ✨ Bridge reranked {len(raw_results)} -> {len(reranked)} results")
        
        return OrthogonalResult(
            items=reranked,
            strategy="bridge",
            query_used=broad_query,
            vibe_profile=vibe,
            target_domain=target_domain
        )
    
    # =========================================================================
    # COMBINED STRATEGIES
    # =========================================================================
    
    async def search_all_strategies(
        self, 
        context: str,
        original_query: str,
        num_results_per_strategy: int = 2,
        include_vector_math: bool = False,
        user_memories: list[Memory] = None
    ) -> list[OrthogonalResult]:
        """
        Run all orthogonal search strategies in parallel.
        
        This gives a diverse set of results:
        - Some from noise-perturbed queries (adjacent clusters)
        - Some from archetype bridging (what the same person would love)
        - Some from cross-domain projection (vibe in different categories)
        - Optionally: results from vector math strategies (PCA, antonym, bridge)
        
        Args:
            context: User's screen context
            original_query: The original search query (for noise injection)
            num_results_per_strategy: Results per strategy
            include_vector_math: Whether to include vector math strategies
            user_memories: User's memories (required for vector math strategies)
            
        Returns:
            List of OrthogonalResults from each strategy
        """
        # First, extract the vibe (shared across strategies)
        vibe = await self.synthesizer.extract_vibe(context)
        
        # Build list of tasks
        tasks = [
            self.search_with_noise(
                original_query, 
                num_results=num_results_per_strategy
            ),
            self.search_via_archetype(
                context,
                vibe=vibe,
                num_results=num_results_per_strategy
            ),
            self.search_cross_domain(
                vibe,
                num_results=num_results_per_strategy
            )
        ]
        
        # Add vector math strategies if requested and we have memories
        if include_vector_math and user_memories and len(user_memories) >= self.settings.pca_min_memories:
            tasks.append(
                self.search_principal_component(
                    user_memories,
                    vibe=vibe,
                    num_results=num_results_per_strategy
                )
            )
            tasks.append(
                self.search_antonym_steering(
                    context,
                    user_memories,
                    vibe=vibe,
                    num_results=num_results_per_strategy
                )
            )
            # Pick a random target domain for bridge search
            source_domain = vibe.source_domain or "content"
            target_domain = random.choice([d for d in self.settings.bridge_domains if d != source_domain])
            tasks.append(
                self.search_bridge_vector(
                    context[:2000],
                    source_domain,
                    target_domain,
                    vibe=vibe,
                    num_results=num_results_per_strategy
                )
            )
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any failed strategies
        valid_results = []
        for r in results:
            if isinstance(r, OrthogonalResult):
                valid_results.append(r)
            else:
                print(f"   ⚠️ Strategy failed: {r}")
        
        return valid_results
    
    async def search_vector_math_only(
        self,
        context: str,
        user_memories: list[Memory],
        num_results_per_strategy: int = 3
    ) -> list[OrthogonalResult]:
        """
        Run ONLY the vector math strategies (PCA, antonym, bridge).
        
        Use this when you want maximum mathematical serendipity without
        the LLM-based strategies.
        
        Args:
            context: User's screen context
            user_memories: User's saved memories from Supermemory
            num_results_per_strategy: Results per strategy
            
        Returns:
            List of OrthogonalResults from vector math strategies
        """
        # Extract vibe for context
        vibe = await self.synthesizer.extract_vibe(context)
        
        tasks = []
        
        # PCA - requires minimum memories
        if len(user_memories) >= self.settings.pca_min_memories:
            tasks.append(
                self.search_principal_component(
                    user_memories,
                    vibe=vibe,
                    num_results=num_results_per_strategy
                )
            )
        
        # Antonym steering
        tasks.append(
            self.search_antonym_steering(
                context,
                user_memories,
                vibe=vibe,
                num_results=num_results_per_strategy
            )
        )
        
        # Bridge vector - pick a target domain
        source_domain = vibe.source_domain or "content"
        available_domains = [d for d in self.settings.bridge_domains if d != source_domain]
        if available_domains:
            target_domain = random.choice(available_domains)
            tasks.append(
                self.search_bridge_vector(
                    context[:2000],
                    source_domain,
                    target_domain,
                    vibe=vibe,
                    num_results=num_results_per_strategy
                )
            )
        
        if not tasks:
            return []
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out failed strategies
        valid_results = []
        for r in results:
            if isinstance(r, OrthogonalResult):
                valid_results.append(r)
            else:
                print(f"   ⚠️ Vector math strategy failed: {r}")
        
        return valid_results
    
    async def _generate_noisy_query(self, query: str, noise_scale: float) -> str:
        """
        Generate a semantically "noisy" variant of the query.
        
        Since we can't directly manipulate Exa's embeddings, we use an LLM
        to generate a query that is semantically adjacent but slightly different.
        
        The noise_scale controls how far we deviate:
        - 0.1: Very close (same topic, different angle)
        - 0.2: Moderate (related concept, different framing)
        - 0.3: Far (tangentially related, unexpected connection)
        """
        # Map noise scale to a qualitative deviation level
        if noise_scale < 0.15:
            deviation = "slightly rephrase with a different angle, keeping the core topic"
        elif noise_scale < 0.25:
            deviation = "shift to a related but distinct concept that shares underlying principles"
        else:
            deviation = "make an unexpected lateral leap to a tangentially connected idea"
        
        system_prompt = f"""Modify this search query to land in a RELATED but DIFFERENT semantic cluster. {deviation}. Return ONLY 5-15 searchable words, no explanation."""

        try:
            response = await self.synthesizer.client.chat.completions.create(
                model=self.synthesizer.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Original query: {query}"}
                ],
                temperature=0.8 + (noise_scale * 0.5),  # Higher temp for more noise
                max_tokens=30
            )
            
            return response.choices[0].message.content.strip().strip('"')
            
        except Exception as e:
            print(f"Noisy query generation error: {e}")
            # Fallback: just return original query
            return query
    
    def combine_results(
        self, 
        orthogonal_results: list[OrthogonalResult],
        max_total: int = 6
    ) -> tuple[list[SearchResult], dict]:
        """
        Combine results from multiple orthogonal strategies.
        
        Uses interleaving to ensure diversity - one from each strategy in rotation.
        
        Returns:
            Tuple of (combined results, metadata about sources)
        """
        combined = []
        metadata = {
            "strategies_used": [],
            "queries_used": [],
            "vibe_profiles": []
        }
        
        # Interleave results from each strategy
        max_per_strategy = (max_total // len(orthogonal_results)) + 1 if orthogonal_results else 0
        
        for result in orthogonal_results:
            metadata["strategies_used"].append(result.strategy)
            metadata["queries_used"].append(result.query_used)
            if result.vibe_profile:
                metadata["vibe_profiles"].append({
                    "emotional_signatures": result.vibe_profile.emotional_signatures,
                    "archetype": result.vibe_profile.archetype[:100] if result.vibe_profile.archetype else "",
                    "source_domain": result.vibe_profile.source_domain
                })
        
        # Round-robin interleaving
        indices = [0] * len(orthogonal_results)
        while len(combined) < max_total:
            added_any = False
            for i, result in enumerate(orthogonal_results):
                if indices[i] < len(result.items) and len(combined) < max_total:
                    combined.append(result.items[indices[i]])
                    indices[i] += 1
                    added_any = True
            if not added_any:
                break
        
        return combined, metadata

