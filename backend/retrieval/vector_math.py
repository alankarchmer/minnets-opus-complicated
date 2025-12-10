"""
Orthogonal Vector Math: True Embedding Arithmetic for Serendipitous Discovery

This module implements mathematical vector operations on embeddings:

1. Principal Component Subtraction (PCA)
   - Identify dominant "genre" vectors via SVD
   - Subtract them to reveal hidden "style" preferences
   - Q_serendipity = V_user - λ * proj_Vdom(V_user)

2. Antonym Steering
   - Steer AWAY from current context, TOWARDS long-term taste
   - Q = V_taste + α * (V_target_vibe - V_current_context)

3. Cross-Modal Bridge Vectors
   - Compute transformation matrices between domains
   - "If this movie were a restaurant, what would it be?"
   - Q = V_content + V_bridge

Key insight: These vectors have no direct text equivalent. We use them to
RERANK broad search results, not to generate text queries directly.
"""

import numpy as np
from typing import Union, Optional
from dataclasses import dataclass

from models import Memory, SearchResult
from config import get_settings


@dataclass
class VectorSearchResult:
    """Result from vector math search with provenance."""
    vector: np.ndarray
    subtracted_tags: list[str]  # What was "removed" (named for LLM context)
    strategy: str  # "pca", "antonym", "bridge"


# Domain anchors for cross-modal bridge vectors
# These should be semantically aligned across domains
DOMAIN_ANCHORS = {
    "restaurant": [
        "cozy restaurant ambiance warmth",
        "fine dining experience elegance",
        "casual eatery atmosphere relaxed",
        "minimalist clean aesthetic dining",
        "chaotic bustling energy food"
    ],
    "movie": [
        "comfort film warmth nostalgia",
        "drama cinema elegance artistic",
        "casual comedy relaxed entertainment",
        "minimalist art-house aesthetic cinema",
        "chaotic thriller energy suspense"
    ],
    "music": [
        "warm acoustic ambient comfort",
        "classical orchestral elegance refined",
        "casual indie relaxed mellow",
        "minimalist electronic aesthetic clean",
        "chaotic noise experimental energy"
    ],
    "book": [
        "cozy literary fiction warmth",
        "literary drama elegance prose",
        "casual reading relaxed light",
        "minimalist poetry aesthetic sparse",
        "chaotic experimental narrative energy"
    ],
    "architecture": [
        "warm wooden interior comfort",
        "classical elegant design refined",
        "casual modern relaxed spaces",
        "minimalist brutalist aesthetic clean",
        "chaotic deconstructivist energy bold"
    ],
}


class OrthogonalVectorMath:
    """
    Core embedding arithmetic for serendipitous discovery.
    
    All methods return normalized vectors suitable for cosine similarity reranking.
    """
    
    def __init__(self, synthesizer):
        """
        Args:
            synthesizer: OpenAISynthesizer instance for embeddings
        """
        self.synthesizer = synthesizer
        self.settings = get_settings()
        self._bridge_vectors: Optional[dict[tuple[str, str], np.ndarray]] = None
        self._domain_centroids: Optional[dict[str, np.ndarray]] = None
    
    async def _get_memory_embeddings(self, memories: list[Memory]) -> np.ndarray:
        """Get embeddings for a list of memories."""
        texts = [m.content[:2000] for m in memories]
        if not texts:
            return np.array([])
        return await self.synthesizer.get_embeddings_batch(texts)
    
    # =========================================================================
    # TECHNIQUE 1: Principal Component Subtraction
    # =========================================================================
    
    async def principal_component_search(
        self, 
        user_memories: list[Memory],
        lambda_surprise: float = None,
        return_subtracted: bool = False
    ) -> Union[np.ndarray, tuple[np.ndarray, list[str]]]:
        """
        Calculate serendipity vector by subtracting dominant taste components.
        
        Math: Q_serendipity = V_user - λ * Σ proj_Vi(V_user) for top k components
        
        The insight: If user loves "Cyberpunk Anime", "Cyberpunk Novels", 
        "Cyberpunk Games" - standard search sees "Cyberpunk" as dominant.
        By subtracting it, we reveal hidden preferences like "Neon Aesthetics"
        or "Anti-establishment themes".
        
        Args:
            user_memories: User's saved memories from Supermemory
            lambda_surprise: Subtraction intensity (default from config)
            return_subtracted: If True, also return names of subtracted components
            
        Returns:
            Normalized serendipity vector, optionally with subtracted tag names
        """
        lambda_val = lambda_surprise or self.settings.pca_lambda_surprise
        
        embeddings = await self._get_memory_embeddings(user_memories)
        
        if len(embeddings) < self.settings.pca_min_memories:
            # Fallback for sparse history - just use average
            result = np.mean(embeddings, axis=0) if len(embeddings) > 0 else np.zeros(1536)
            if return_subtracted:
                return result / (np.linalg.norm(result) + 1e-10), []
            return result / (np.linalg.norm(result) + 1e-10)
        
        # Compute user centroid
        v_user = np.mean(embeddings, axis=0)
        
        # Center the data for SVD
        centered = embeddings - v_user
        
        # SVD with robustness check
        try:
            U, S, Vt = np.linalg.svd(centered, full_matrices=False)
        except np.linalg.LinAlgError:
            # Add tiny noise to break symmetry/singularity
            noise = np.random.normal(0, 1e-9, centered.shape)
            U, S, Vt = np.linalg.svd(centered + noise, full_matrices=False)
        
        # Subtract top k dominant components
        q_serendipity = v_user.copy()
        subtracted_tags = []
        
        num_components = min(self.settings.pca_num_components, len(Vt))
        
        for i in range(num_components):
            v_dominant = Vt[i]
            projection = np.dot(v_user, v_dominant) * v_dominant
            q_serendipity -= lambda_val * projection
            
            # "NAME THE GHOST": Find memory that most defines this axis
            if return_subtracted:
                scores = [np.dot(emb - v_user, v_dominant) for emb in embeddings]
                top_idx = int(np.argmax(np.abs(scores)))
                # Extract a snippet from the memory that defines this component
                subtracted_tags.append(user_memories[top_idx].content[:80])
        
        # Normalize
        norm = np.linalg.norm(q_serendipity)
        q_norm = q_serendipity / (norm + 1e-10)
        
        if return_subtracted:
            return q_norm, subtracted_tags
        return q_norm
    
    # =========================================================================
    # TECHNIQUE 2: Antonym Steering (Directional, not pure negation)
    # =========================================================================
    
    async def antonym_steering_search(
        self,
        current_context: str,
        user_memories: list[Memory],
        target_vibe: str = None,
        alpha: float = None
    ) -> tuple[np.ndarray, str]:
        """
        Steer AWAY from current context, TOWARDS a target vibe, weighted by taste.
        
        Math: Q = V_taste + α * (V_target_vibe - V_current_context)
        
        Unlike pure negation (-1 * V_context), this gives the steering a 
        direction. We move TOWARDS something (novelty, relaxation) not just
        away from the current state.
        
        Example: User in sterile office → steer towards "cozy, chaotic, intimate"
        
        Args:
            current_context: User's current screen content
            user_memories: User's saved memories (for long-term taste)
            target_vibe: Target vibe anchor (default: random from config)
            alpha: Steering strength (default from config)
            
        Returns:
            Tuple of (normalized steering vector, target_vibe used)
        """
        alpha_val = alpha or self.settings.antonym_alpha
        
        # 1. V_LongTermTaste from Supermemory
        if user_memories and len(user_memories) > 0:
            memory_embeddings = await self._get_memory_embeddings(user_memories)
            v_taste = np.mean(memory_embeddings, axis=0)
        else:
            # Fallback: neutral vector
            v_taste = np.zeros(1536)
        
        # 2. V_CurrentContext from screen content
        v_context = await self.synthesizer.get_embedding(current_context[:4000])
        v_context = np.array(v_context)
        
        # 3. V_TargetVibe - pick a target direction
        if target_vibe is None:
            import random
            target_vibe = random.choice(self.settings.antonym_target_vibes)
        
        v_target = await self.synthesizer.get_embedding(target_vibe)
        v_target = np.array(v_target)
        
        # 4. Directional steering: taste + α * (target - context)
        direction = v_target - v_context
        q_final = v_taste + alpha_val * direction
        
        # Normalize
        norm = np.linalg.norm(q_final)
        q_norm = q_final / (norm + 1e-10)
        
        return q_norm, target_vibe
    
    # =========================================================================
    # TECHNIQUE 3: Cross-Modal Bridge Vectors
    # =========================================================================
    
    async def compute_bridge_vectors(self) -> dict[tuple[str, str], np.ndarray]:
        """
        Pre-compute domain transformation vectors.
        
        V_bridge = V_AvgDomain1 - V_AvgDomain2
        
        This allows "If this movie were a restaurant, what would it be?"
        by adding the bridge vector to content embeddings.
        
        Returns:
            Dictionary mapping (target_domain, source_domain) to bridge vectors
        """
        if self._bridge_vectors is not None:
            return self._bridge_vectors
        
        # Compute domain centroids
        self._domain_centroids = {}
        for domain, anchors in DOMAIN_ANCHORS.items():
            embeddings = await self.synthesizer.get_embeddings_batch(anchors)
            self._domain_centroids[domain] = np.mean(embeddings, axis=0)
        
        # Compute all pairwise bridge vectors
        self._bridge_vectors = {}
        for d1 in self._domain_centroids:
            for d2 in self._domain_centroids:
                if d1 != d2:
                    # Bridge from d2 to d1: add this to d2 content to get d1 equivalent
                    self._bridge_vectors[(d1, d2)] = (
                        self._domain_centroids[d1] - self._domain_centroids[d2]
                    )
        
        return self._bridge_vectors
    
    async def bridge_vector_search(
        self,
        content: str,
        source_domain: str,
        target_domain: str
    ) -> np.ndarray:
        """
        Transform content from one domain to another.
        
        Math: Q = V_content + V_bridge
        
        Example: Take a movie the user loves, add bridge vector to find
        what restaurant would give the same "feeling".
        
        Args:
            content: Text content to transform
            source_domain: Original domain (e.g., "movie")
            target_domain: Target domain (e.g., "restaurant")
            
        Returns:
            Normalized transformed vector
        """
        # Ensure bridge vectors are computed
        bridges = await self.compute_bridge_vectors()
        
        # Get content embedding
        v_content = await self.synthesizer.get_embedding(content[:4000])
        v_content = np.array(v_content)
        
        # Apply bridge transformation
        bridge_key = (target_domain, source_domain)
        if bridge_key not in bridges:
            # Unknown domain pair - return content vector as-is
            print(f"   Warning: No bridge for {source_domain} -> {target_domain}")
            return v_content / (np.linalg.norm(v_content) + 1e-10)
        
        v_bridge = bridges[bridge_key]
        q = v_content + v_bridge
        
        # Normalize
        norm = np.linalg.norm(q)
        return q / (norm + 1e-10)
    
    # =========================================================================
    # RERANKING: Use math vectors to rerank broad search results
    # =========================================================================
    
    async def rerank_by_vector(
        self,
        results: list[SearchResult],
        target_vector: np.ndarray,
        top_k: int = None
    ) -> list[SearchResult]:
        """
        Rerank search results by cosine similarity to target vector.
        
        This is the key integration point: we can't search Exa with raw vectors,
        so we fetch broad results and rerank them mathematically.
        
        Performance: Uses batch embeddings + vectorized cosine similarity
        to avoid the "10-second hang" of sequential API calls.
        
        Args:
            results: Search results from Exa (broad pool)
            target_vector: Mathematical target (from PCA, antonym, or bridge)
            top_k: Number of results to return (default from config)
            
        Returns:
            Top-k results sorted by similarity to target vector
        """
        top_k = top_k or self.settings.rerank_top_k
        
        if not results:
            return []
        
        # 1. Extract texts
        texts = [r.text[:2000] if r.text else r.title for r in results]
        
        # 2. BATCH EMBEDDING (single API call - crucial for performance)
        embeddings_matrix = await self.synthesizer.get_embeddings_batch(texts)
        
        # 3. VECTORIZED cosine similarity (no loop)
        # Normalize embeddings
        norms = np.linalg.norm(embeddings_matrix, axis=1)
        # Avoid division by zero
        norms = np.where(norms == 0, 1e-10, norms)
        
        target_norm = np.linalg.norm(target_vector)
        if target_norm == 0:
            target_norm = 1e-10
        
        # Dot product of target vs all candidates at once
        similarities = np.dot(embeddings_matrix, target_vector) / (norms * target_norm)
        
        # 4. Sort and return top-k
        scored = list(zip(results, similarities))
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [r for r, _ in scored[:top_k]]
    
    def cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))
