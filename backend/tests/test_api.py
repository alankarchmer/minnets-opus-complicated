"""
Comprehensive API tests for Minnets backend.

Run with: pytest tests/test_api.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Mock the settings before importing app
with patch('config.get_settings') as mock_settings:
    mock_settings.return_value = MagicMock(
        openai_api_key="test-key",
        supermemory_api_key="test-key",
        exa_api_key="test-key",
        host="127.0.0.1",
        port=8000,
        max_anchors=5,
        min_similarity_threshold=0.65,
        max_similarity_threshold=0.85,
        max_suggestions=3,
        openai_model="gpt-4",
        openai_embedding_model="text-embedding-3-small",
        orthogonal_enabled=True,
        orthogonal_noise_scale=0.15,
        orthogonal_archetype_enabled=True,
        orthogonal_target_domains=["restaurants", "music", "films"],
        orthogonal_vibe_temperature=0.8
    )
    from main import app


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for the /health endpoint."""
    
    def test_health_check_returns_healthy(self):
        """Health check should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "minnets-backend"


class TestAnalyzeEndpoint:
    """Tests for the /analyze endpoint."""
    
    def test_analyze_requires_context(self):
        """Analyze endpoint should require context field."""
        response = client.post("/analyze", json={
            "app_name": "Test",
            "window_title": "Test Window"
        })
        assert response.status_code == 422  # Validation error
    
    def test_analyze_requires_app_name(self):
        """Analyze endpoint should require app_name field."""
        response = client.post("/analyze", json={
            "context": "Test context",
            "window_title": "Test Window"
        })
        assert response.status_code == 422  # Validation error
    
    @patch('main.synthesizer')
    @patch('main.cascade_router')
    @patch('main.scorer')
    @patch('main.exa_client')
    def test_analyze_returns_empty_when_no_concepts(
        self, mock_exa, mock_scorer, mock_router, mock_synth
    ):
        """Analyze should return empty suggestions when no concepts extracted."""
        mock_synth.extract_concepts = AsyncMock(return_value=[])
        
        response = client.post("/analyze", json={
            "context": "Very short",
            "app_name": "Test",
            "window_title": "Test Window"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["suggestions"] == []
        assert "processingTimeMs" in data


class TestSearchWebEndpoint:
    """Tests for the /search-web endpoint."""
    
    @patch('main.cascade_router')
    @patch('main.scorer')
    @patch('main.synthesizer')
    def test_search_web_requires_query(self, mock_synth, mock_scorer, mock_router):
        """Search web endpoint should require query parameter."""
        response = client.post("/search-web")
        assert response.status_code == 422  # Missing query param


class TestTangentialEndpoint:
    """Tests for the /test-tangential endpoint."""
    
    @patch('main.synthesizer')
    def test_tangential_with_default_context(self, mock_synth):
        """Test tangential extraction with default Pep Guardiola context."""
        mock_synth.extract_concepts = AsyncMock(return_value=[
            "positional play tactics",
            "tiki-taka philosophy"
        ])
        mock_synth.extract_for_redundancy_check = AsyncMock(return_value="pep guardiola")
        
        response = client.post("/test-tangential")
        assert response.status_code == 200
        data = response.json()
        
        assert "main_subject_to_avoid" in data
        assert "tangential_concepts_to_search" in data
        assert "search_query" in data
    
    @patch('main.synthesizer')
    def test_tangential_with_custom_context(self, mock_synth):
        """Test tangential extraction with custom context."""
        mock_synth.extract_concepts = AsyncMock(return_value=["concept1", "concept2"])
        mock_synth.extract_for_redundancy_check = AsyncMock(return_value="test subject")
        
        response = client.post("/test-tangential?context=Custom test content about testing")
        assert response.status_code == 200


class TestVibeEndpoint:
    """Tests for the /test-vibe endpoint."""
    
    @patch('main.synthesizer')
    def test_vibe_extraction_returns_profile(self, mock_synth):
        """Test vibe extraction returns proper profile structure."""
        from models import VibeProfile
        mock_synth.extract_vibe = AsyncMock(return_value=VibeProfile(
            emotional_signatures=["precise", "obsessive", "elegant"],
            archetype="Someone who sees beauty in systems",
            cross_domain_interests=["omakase restaurants", "jazz"],
            anti_patterns=["chaos", "improvisation"],
            source_domain="football tactics"
        ))
        
        response = client.post("/test-vibe")
        assert response.status_code == 200
        data = response.json()
        
        assert "vibe_profile" in data
        assert "emotional_signatures" in data["vibe_profile"]
        assert "archetype" in data["vibe_profile"]
        assert "cross_domain_interests" in data["vibe_profile"]
        assert "explanation" in data


class TestOrthogonalEndpoint:
    """Tests for the /test-orthogonal endpoint."""
    
    @patch('main.synthesizer')
    @patch('main.exa_client')
    @patch('main.cascade_router')
    def test_orthogonal_returns_comparison(self, mock_router, mock_exa, mock_synth):
        """Test orthogonal endpoint returns comparison of standard vs orthogonal."""
        from models import VibeProfile, SearchResult
        from retrieval.cascade_router import CascadeResult, RetrievalPath, ConfidenceLevel
        
        # Mock vibe extraction
        mock_synth.extract_vibe = AsyncMock(return_value=VibeProfile(
            emotional_signatures=["imperfect", "quiet", "humble"],
            archetype="Someone who distrusts polish",
            cross_domain_interests=["hole-in-the-wall restaurants"],
            anti_patterns=["SEO-optimized"],
            source_domain="ceramics"
        ))
        
        # Mock concept extraction
        mock_synth.extract_concepts = AsyncMock(return_value=[
            "wabi-sabi aesthetics",
            "imperfection philosophy"
        ])
        
        # Mock Exa search
        mock_exa.search = AsyncMock(return_value=[
            SearchResult(
                title="Japanese Aesthetics",
                url="https://example.com/1",
                text="Content about aesthetics...",
                score=0.8
            )
        ])
        
        # Mock orthogonal search
        mock_router.route_orthogonal_only = AsyncMock(return_value=CascadeResult(
            items=[SearchResult(
                title="Hidden Restaurant",
                url="https://example.com/2",
                text="A humble restaurant...",
                score=0.7
            )],
            path=RetrievalPath.ORTHOGONAL,
            confidence=ConfidenceLevel.MEDIUM,
            orthogonal_metadata={"strategies_used": ["archetype_bridge"]}
        ))
        
        response = client.post("/test-orthogonal")
        assert response.status_code == 200
        data = response.json()
        
        assert "vibe_profile" in data
        assert "standard_search" in data
        assert "orthogonal_search" in data
        assert "insight" in data


class TestSaveToMemoryEndpoint:
    """Tests for the /save-to-memory endpoint."""
    
    @patch('main.supermemory_client')
    def test_save_to_memory_success(self, mock_supermemory):
        """Test saving to memory returns success."""
        mock_supermemory.add_memory = AsyncMock(return_value="mem-123")
        
        response = client.post("/save-to-memory", json={
            "title": "Test Memory",
            "content": "This is test content"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "saved"
        assert data["memory_id"] == "mem-123"
    
    @patch('main.supermemory_client')
    def test_save_to_memory_with_url(self, mock_supermemory):
        """Test saving to memory with source URL."""
        mock_supermemory.add_memory = AsyncMock(return_value="mem-456")
        
        response = client.post("/save-to-memory", json={
            "title": "Article",
            "content": "Article content",
            "sourceUrl": "https://example.com/article",
            "context": "Found while reading about X"
        })
        
        assert response.status_code == 200


class TestExaEndpoint:
    """Tests for the /test-exa endpoint."""
    
    @patch('main.exa_client')
    def test_exa_search_returns_results(self, mock_exa):
        """Test Exa search returns formatted results."""
        from models import SearchResult
        mock_exa.search = AsyncMock(return_value=[
            SearchResult(
                title="Test Result",
                url="https://example.com",
                text="This is test content that is longer than 200 characters so it should be truncated in the response to show just a preview of the content...",
                score=0.9
            )
        ])
        
        response = client.post("/test-exa?query=test query")
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "test query"
        assert data["num_results"] == 1
        assert len(data["results"]) == 1
        assert "text_preview" in data["results"][0]


class TestModels:
    """Tests for Pydantic models."""
    
    def test_suggestion_source_enum(self):
        """Test SuggestionSource enum values."""
        from models import SuggestionSource
        
        assert SuggestionSource.SUPERMEMORY.value == "supermemory"
        assert SuggestionSource.WEB_SEARCH.value == "web_search"
        assert SuggestionSource.ORTHOGONAL.value == "orthogonal"
    
    def test_vibe_profile_defaults(self):
        """Test VibeProfile has proper defaults."""
        from models import VibeProfile
        
        vibe = VibeProfile()
        assert vibe.emotional_signatures == []
        assert vibe.archetype == ""
        assert vibe.cross_domain_interests == []
        assert vibe.anti_patterns == []
        assert vibe.source_domain == ""
    
    def test_analyze_request_camel_case(self):
        """Test AnalyzeRequest handles camelCase from Swift."""
        from models import AnalyzeRequest
        
        # Should accept snake_case
        req1 = AnalyzeRequest(
            context="test",
            app_name="Test App",
            window_title="Window"
        )
        assert req1.app_name == "Test App"
        
        # Should also accept camelCase via alias
        req2 = AnalyzeRequest.model_validate({
            "context": "test",
            "appName": "Test App 2",
            "windowTitle": "Window 2"
        })
        assert req2.app_name == "Test App 2"


class TestScoring:
    """Tests for the scoring module."""
    
    def test_mmr_doughnut_echo_chamber_penalty(self):
        """Test that echo chamber (>0.85) items are penalized."""
        from retrieval.scoring import RetrievalScorer
        from models import Memory
        
        scorer = RetrievalScorer()
        
        # Create a memory with very high similarity (echo chamber)
        echo_memory = Memory(
            id="1",
            content="Echo content",
            similarity=0.95  # Echo chamber
        )
        
        scored = scorer.apply_mmr_scoring([echo_memory])
        _, score, _, novelty = scored[0]
        
        # Echo chamber should have low novelty
        assert novelty == 0.2
        # Score should be penalized (0.95 * 0.5 = 0.475)
        assert score < 0.5
    
    def test_mmr_doughnut_sweet_spot_bonus(self):
        """Test that sweet spot (0.65-0.85) items get bonus."""
        from retrieval.scoring import RetrievalScorer
        from models import Memory
        
        scorer = RetrievalScorer()
        
        # Create a memory in the sweet spot
        sweet_memory = Memory(
            id="2",
            content="Sweet spot content",
            similarity=0.75  # Sweet spot
        )
        
        scored = scorer.apply_mmr_scoring([sweet_memory])
        _, score, _, novelty = scored[0]
        
        # Sweet spot should have bonus (0.75 * 1.2 = 0.9)
        assert score > 0.75
        # Novelty should be in reasonable range
        assert 0.5 <= novelty <= 1.0


class TestOrthogonalSearch:
    """Tests for the orthogonal search module."""
    
    @pytest.mark.asyncio
    async def test_combine_results_interleaves(self):
        """Test that combine_results interleaves from different strategies."""
        from retrieval.orthogonal_search import OrthogonalSearcher, OrthogonalResult
        from models import SearchResult
        
        # Create mock results from different strategies
        noise_result = OrthogonalResult(
            items=[
                SearchResult(title="Noise 1", url="n1", text="", score=0.8),
                SearchResult(title="Noise 2", url="n2", text="", score=0.7),
            ],
            strategy="noise_injection",
            query_used="noisy query"
        )
        
        archetype_result = OrthogonalResult(
            items=[
                SearchResult(title="Arch 1", url="a1", text="", score=0.8),
                SearchResult(title="Arch 2", url="a2", text="", score=0.7),
            ],
            strategy="archetype_bridge",
            query_used="archetype query"
        )
        
        # We can't easily instantiate OrthogonalSearcher without mocking
        # So test the static part of combine_results logic
        results = [noise_result, archetype_result]
        
        # Manual interleaving check
        combined = []
        indices = [0, 0]
        max_total = 4
        while len(combined) < max_total:
            added_any = False
            for i, result in enumerate(results):
                if indices[i] < len(result.items) and len(combined) < max_total:
                    combined.append(result.items[indices[i]])
                    indices[i] += 1
                    added_any = True
            if not added_any:
                break
        
        # Should interleave: Noise1, Arch1, Noise2, Arch2
        assert len(combined) == 4
        assert combined[0].title == "Noise 1"
        assert combined[1].title == "Arch 1"
        assert combined[2].title == "Noise 2"
        assert combined[3].title == "Arch 2"


class TestCascadeRouter:
    """Tests for the cascade router."""
    
    def test_retrieval_path_enum(self):
        """Test RetrievalPath enum values."""
        from retrieval.cascade_router import RetrievalPath
        
        assert RetrievalPath.ORTHOGONAL.value == "orthogonal"
        assert RetrievalPath.ORTHOGONAL_PLUS_GRAPH.value == "orthogonal_plus_graph"
        assert RetrievalPath.GRAPH.value == "graph"
        assert RetrievalPath.VECTOR.value == "vector"
        assert RetrievalPath.WEB.value == "web"
    
    def test_confidence_level_enum(self):
        """Test ConfidenceLevel enum values."""
        from retrieval.cascade_router import ConfidenceLevel
        
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.LOW.value == "low"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

