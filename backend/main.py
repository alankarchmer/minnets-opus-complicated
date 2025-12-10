import time
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    AnalyzeRequest, 
    AnalyzeResponse, 
    SaveToMemoryRequest,
    FeedbackRequest
)
from retrieval.exa_search import ExaSearchClient
from retrieval.supermemory import SupermemoryClient
from retrieval.scoring import RetrievalScorer
from retrieval.cascade_router import CascadeRouter, RetrievalPath, ConfidenceLevel
from retrieval.judge_logger import JudgeLogger
from synthesis.openai_client import OpenAISynthesizer
from synthesis.context_judge import ContextJudge
from config import get_settings


# Global instances
exa_client: ExaSearchClient = None
supermemory_client: SupermemoryClient = None
synthesizer: OpenAISynthesizer = None
scorer: RetrievalScorer = None
cascade_router: CascadeRouter = None
context_judge: ContextJudge = None
judge_logger: JudgeLogger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global exa_client, supermemory_client, synthesizer, scorer, cascade_router
    global context_judge, judge_logger
    
    exa_client = ExaSearchClient()
    supermemory_client = SupermemoryClient()
    synthesizer = OpenAISynthesizer()
    scorer = RetrievalScorer()
    cascade_router = CascadeRouter(synthesizer=synthesizer)
    context_judge = ContextJudge()
    judge_logger = JudgeLogger()
    
    print("🧠 Minnets backend started")
    print("   Using CascadeRouter with LLM Context Judge")
    print("   🧠 Context Judge: LLM-based cognitive state analysis")
    print("   📊 Allocation-based routing (not binary gating)")
    print("   🎲 Orthogonal Search: noise injection, archetype bridge, cross-domain vibe")
    print("   Graph Pivot: Echo chamber filter + neighbor pivoting")
    print("   Using Exa.ai for web search (with redundancy filtering)")
    print("   Using Supermemory for knowledge base")
    print("   Using OpenAI for synthesis + vibe extraction")
    print("   📝 Logging decisions for future training")
    yield
    
    await cascade_router.close()
    await supermemory_client.close()
    print("Minnets backend stopped")


app = FastAPI(
    title="Minnets Backend",
    description="Proactive knowledge companion - retrieval and synthesis API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "minnets-backend"}


@app.post("/analyze", response_model=AnalyzeResponse, response_model_by_alias=True)
async def analyze_context(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Main analysis endpoint with LLM Context Judge.
    
    Takes user's screen context and returns proactive suggestions.
    
    Flow:
    1. Context Judge analyzes cognitive state -> StrategyWeights
    2. Weighted routing allocates resources across strategies
    3. Results are boosted based on intent/source match
    4. Top suggestions synthesized and returned
    
    KEY INSIGHT: We search for TANGENTIAL concepts, not the main subject.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())[:8]  # Short ID for logging
    
    print(f"\n📥 [{request_id}] Analyzing context from: {request.app_name}")
    print(f"   Context length: {len(request.context)} chars")
    
    context = request.context
    
    # Check if context contains a URL that we should fetch content for
    current_url = None
    if "CURRENT_URL:" in context:
        try:
            url_line = [line for line in context.split("\n") if "CURRENT_URL:" in line][0]
            current_url = url_line.replace("CURRENT_URL:", "").strip()
            
            if current_url and not current_url.startswith("chrome://") and not current_url.startswith("about:"):
                print(f"   🌐 Fetching content from URL: {current_url}")
                
                # Use Exa to get the content of this specific URL
                url_content = await exa_client.get_contents([current_url])
                
                if url_content and len(url_content) > 0:
                    fetched = url_content[0]
                    context = f"Page Title: {fetched.title}\nURL: {current_url}\n\nContent:\n{fetched.text[:8000]}"
                    print(f"   ✓ Fetched {len(fetched.text)} chars from URL")
                else:
                    print(f"   ⚠️ Could not fetch URL content, using original context")
        except Exception as e:
            print(f"   ⚠️ Error fetching URL: {e}")
    
    try:
        # Step 0: Context Judge - Analyze cognitive state
        print("   🧠 Running Context Judge...")
        weights = await context_judge.analyze(
            context=context,
            app_name=request.app_name,
            window_title=request.window_title
        )
        
        # Step 1: Extract TANGENTIAL concepts (NOT the main subject)
        print("   Extracting tangential concepts...")
        concepts = await synthesizer.extract_concepts(
            context, 
            request.app_name
        )
        
        if not concepts:
            print("   No concepts extracted")
            return AnalyzeResponse(
                suggestions=[],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        print(f"   🔗 Will search for: {concepts}")
        
        # Step 2: Build search query from tangential concepts
        search_query = " ".join(concepts[:3])
        print(f"   🔍 Searching for: '{search_query}'")
        
        # Step 3: Weighted routing based on Context Judge
        cascade_result = await cascade_router.route_weighted(
            query=search_query,
            context=context,
            weights=weights
        )
        
        print(f"   Path: {cascade_result.path.value}, Confidence: {cascade_result.confidence.value}")
        
        if not cascade_result.items:
            print("   No results found")
            return AnalyzeResponse(
                suggestions=[],
                processing_time_ms=int((time.time() - start_time) * 1000),
                retrieval_path=cascade_result.path.value,
                confidence=cascade_result.confidence.value,
                graph_insight=cascade_result.graph_insight,
                should_offer_web=cascade_result.should_offer_web
            )
        
        # Step 4: Synthesize suggestions (emphasizing what's DIFFERENT)
        print("   Synthesizing suggestions (emphasizing novelty)...")
        suggestions = []
        
        # Score items for synthesis (cascade_result.items already ranked)
        scored_items = scorer.filter_and_rank(cascade_result.items, max_results=3)
        
        for item, score, rel_score, nov_score in scored_items:
            suggestion = await synthesizer.synthesize_suggestion(
                item=item,
                context=request.context,
                relevance_score=rel_score,
                novelty_score=nov_score
            )
            suggestions.append(suggestion)
        
        processing_time = int((time.time() - start_time) * 1000)
        print(f"   ✅ Generated {len(suggestions)} suggestions in {processing_time}ms")
        print(f"   Retrieval: {cascade_result.path.value} ({cascade_result.confidence.value} confidence)")
        
        # Step 5: Log decision for training
        await judge_logger.log_decision(
            request_id=request_id,
            app_name=request.app_name,
            window_title=request.window_title,
            weights=weights,
            insight_ids=[s.id for s in suggestions],
            context_len=len(context),
            retrieval_path=cascade_result.path.value
        )
        
        return AnalyzeResponse(
            suggestions=suggestions,
            processing_time_ms=processing_time,
            retrieval_path=cascade_result.path.value,
            confidence=cascade_result.confidence.value,
            graph_insight=cascade_result.graph_insight,
            should_offer_web=cascade_result.should_offer_web
        )
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search-web")
async def trigger_web_search(query: str):
    """
    Explicit web search endpoint.
    Called when user clicks "Search Web" button (when should_offer_web is true).
    """
    print(f"\n🌐 User triggered web search: '{query}'")
    
    start_time = time.time()
    
    try:
        web_results = await cascade_router.trigger_web_search(query)
        print(f"   Found {len(web_results)} web results")
        
        # Score and synthesize
        scored_items = scorer.filter_and_rank(web_results, max_results=3)
        
        suggestions = []
        for item, score, rel_score, nov_score in scored_items:
            suggestion = await synthesizer.synthesize_suggestion(
                item=item,
                context=query,  # Use query as context for web results
                relevance_score=rel_score,
                novelty_score=nov_score
            )
            suggestions.append(suggestion)
        
        processing_time = int((time.time() - start_time) * 1000)
        print(f"   ✅ Generated {len(suggestions)} web suggestions in {processing_time}ms")
        
        return AnalyzeResponse(
            suggestions=suggestions,
            processing_time_ms=processing_time,
            retrieval_path=RetrievalPath.WEB.value,
            confidence=ConfidenceLevel.LOW.value,
            graph_insight=False,
            should_offer_web=False
        )
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback")
async def log_feedback(request: FeedbackRequest):
    """
    Log user feedback on an insight for training data collection.
    
    Accepts both implicit signals (click, dwell, dismiss) and 
    explicit signals (thumbs_up, thumbs_down, save).
    
    This data is used to:
    1. Evaluate which context types -> which weights -> positive outcomes
    2. Train personalized models per user
    3. Fine-tune the Context Judge prompts
    """
    print(f"\n📝 Feedback: {request.feedback_type.value} on insight {request.insight_id}")
    
    try:
        await judge_logger.log_feedback(
            request_id=request.request_id,
            insight_id=request.insight_id,
            feedback_type=request.feedback_type.value,
            dwell_time_ms=request.dwell_time_ms,
            position_in_list=request.position_in_list,
            metadata=request.metadata
        )
        
        return {
            "status": "logged",
            "request_id": request.request_id,
            "insight_id": request.insight_id,
            "feedback_type": request.feedback_type.value
        }
        
    except Exception as e:
        print(f"   ⚠️ Feedback logging error: {e}")
        # Don't fail the request if logging fails
        return {
            "status": "error",
            "message": str(e)
        }


@app.post("/test-exa")
async def test_exa(query: str = "transformer architecture machine learning"):
    """Test endpoint to verify Exa search is working."""
    print(f"\n🔍 Testing Exa search: '{query}'")
    
    try:
        results = await exa_client.search(query, num_results=3)
        
        return {
            "query": query,
            "num_results": len(results),
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "text_preview": r.text[:200] + "..." if len(r.text) > 200 else r.text
                }
                for r in results
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/test-tangential")
async def test_tangential_extraction(context: str = ""):
    """
    Test endpoint to see what tangential concepts are extracted.
    Useful for debugging the redundancy avoidance logic.
    """
    if not context:
        context = """Pep Guardiola - Wikipedia
        Josep "Pep" Guardiola Sala is a Spanish professional football manager 
        and former player who is the manager of Manchester City. He is one of 
        the most successful managers in football history, having won multiple 
        league titles and Champions League trophies with Barcelona, Bayern Munich, 
        and Manchester City."""
    
    print(f"\n🧪 Testing tangential extraction...")
    
    try:
        concepts = await synthesizer.extract_concepts(context, "Test")
        main_subject = await synthesizer.extract_for_redundancy_check(context)
        
        return {
            "main_subject_to_avoid": main_subject,
            "tangential_concepts_to_search": concepts,
            "search_query": " ".join(concepts[:3]) if concepts else ""
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/test-orthogonal")
async def test_orthogonal_search(context: str = ""):
    """
    Test endpoint to compare standard vs orthogonal retrieval.
    
    Shows side-by-side comparison of:
    - Standard tangential search results
    - Orthogonal search results (noise injection, archetype bridge, cross-domain)
    - Vibe profile extracted from context
    
    This demonstrates the "tangential leap" capability - finding content that
    would delight the same TYPE OF PERSON, not just similar content.
    """
    if not context:
        # Default test case: wabi-sabi pottery (great for cross-domain vibes)
        context = """Wabi-sabi - Wikipedia
        
        In traditional Japanese aesthetics, wabi-sabi (侘び寂び) is a world view 
        centered on the acceptance of transience and imperfection. The aesthetic 
        is sometimes described as one of appreciating beauty that is "imperfect, 
        impermanent, and incomplete" in nature.
        
        Characteristics of wabi-sabi aesthetics and principles include asymmetry, 
        roughness, simplicity, economy, austerity, modesty, intimacy, and the 
        appreciation of both natural objects and the forces of nature.
        
        Wabi-sabi can change our perception of the world to the point where a chip 
        or crack in a vase makes it more interesting and gives the object a 
        greater meditative value. Similarly, peeling bark, rust, and other marks 
        of aging become valued."""
    
    print(f"\n🎲 Testing orthogonal search...")
    start_time = time.time()
    
    try:
        # Step 1: Extract vibe profile
        print("   Extracting vibe profile...")
        vibe = await synthesizer.extract_vibe(context, "Test")
        
        # Step 2: Extract tangential concepts for standard search
        concepts = await synthesizer.extract_concepts(context, "Test")
        search_query = " ".join(concepts[:3]) if concepts else "aesthetics philosophy"
        
        # Step 3: Run standard search
        print(f"   Standard search: '{search_query}'")
        standard_results = await exa_client.search(search_query, num_results=3)
        
        # Step 4: Run orthogonal search (all strategies)
        print("   Running orthogonal search strategies...")
        orthogonal_result = await cascade_router.route_orthogonal_only(
            context=context,
            query=search_query
        )
        
        processing_time = int((time.time() - start_time) * 1000)
        
        # Format results for comparison
        return {
            "processing_time_ms": processing_time,
            
            # Vibe Profile - the "type of person" extracted
            "vibe_profile": {
                "emotional_signatures": vibe.emotional_signatures,
                "archetype": vibe.archetype,
                "cross_domain_interests": vibe.cross_domain_interests,
                "anti_patterns": vibe.anti_patterns,
                "source_domain": vibe.source_domain
            },
            
            # Standard search - what tangential concepts found
            "standard_search": {
                "query": search_query,
                "tangential_concepts": concepts,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "text_preview": r.text[:300] + "..." if len(r.text) > 300 else r.text
                    }
                    for r in standard_results
                ]
            },
            
            # Orthogonal search - cross-domain serendipity
            "orthogonal_search": {
                "path": orthogonal_result.path.value,
                "metadata": orthogonal_result.orthogonal_metadata,
                "results": [
                    {
                        "title": r.title,
                        "url": r.url,
                        "text_preview": r.text[:300] + "..." if len(r.text) > 300 else r.text
                    }
                    for r in orthogonal_result.items
                ] if orthogonal_result.items else []
            },
            
            # Key insight for user
            "insight": f"Standard search finds content ABOUT {vibe.source_domain or 'the topic'}. "
                      f"Orthogonal search finds content that would delight someone who values: "
                      f"{', '.join(vibe.emotional_signatures[:3]) if vibe.emotional_signatures else 'similar aesthetics'}."
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/test-vibe")
async def test_vibe_extraction(context: str = ""):
    """
    Test endpoint to see the full vibe profile extracted from content.
    
    The vibe profile is the key to cross-domain serendipity - it captures
    the TYPE OF PERSON who appreciates this content, not just the topic.
    """
    if not context:
        context = """Pep Guardiola - Wikipedia
        Josep "Pep" Guardiola Sala is a Spanish professional football manager 
        and former player who is the manager of Manchester City. He is one of 
        the most successful managers in football history, having won multiple 
        league titles and Champions League trophies with Barcelona, Bayern Munich, 
        and Manchester City.
        
        Guardiola is known for his tactical innovations, particularly his use of 
        positional play, high pressing, and building from the back. His teams 
        are characterized by fluid passing, constant movement, and dominating 
        possession."""
    
    print(f"\n🎭 Testing vibe extraction...")
    
    try:
        vibe = await synthesizer.extract_vibe(context, "Test")
        
        return {
            "vibe_profile": {
                "emotional_signatures": vibe.emotional_signatures,
                "archetype": vibe.archetype,
                "cross_domain_interests": vibe.cross_domain_interests,
                "anti_patterns": vibe.anti_patterns,
                "source_domain": vibe.source_domain
            },
            "explanation": "This vibe profile captures WHO would appreciate this content. "
                          "Cross-domain interests show what else they might love."
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/test-context-judge")
async def test_context_judge(
    context: str = "",
    app_name: str = "Safari",
    window_title: str = "Test"
):
    """
    Test endpoint to see how the Context Judge classifies different contexts.
    
    Shows the strategy weights determined by the LLM for a given context.
    Useful for debugging and tuning the judge prompt.
    """
    if not context:
        context = """Pep Guardiola - Wikipedia
        Josep "Pep" Guardiola Sala is a Spanish professional football manager 
        and former player who is the manager of Manchester City."""
    
    print(f"\n🧠 Testing Context Judge...")
    
    try:
        weights = await context_judge.analyze(
            context=context,
            app_name=app_name,
            window_title=window_title
        )
        
        return {
            "app_name": app_name,
            "window_title": window_title,
            "context_preview": context[:200] + "..." if len(context) > 200 else context,
            "weights": {
                "serendipity": weights.serendipity,
                "relevance": weights.relevance,
                "source_web": weights.source_web,
                "source_local": weights.source_local,
                "reasoning": weights.reasoning
            },
            "interpretation": {
                "intent": "serendipity" if weights.serendipity > weights.relevance else "relevance",
                "source": "web" if weights.source_web > weights.source_local else "local",
                "web_budget": f"{int(weights.source_web * 10)} results",
                "local_budget": f"{int(weights.source_local * 10)} results"
            }
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e)}


@app.post("/save-to-memory")
async def save_to_memory(request: SaveToMemoryRequest):
    """
    Save a suggestion to Supermemory knowledge base.
    This populates your KB with interesting findings from web search.
    """
    title = request.title
    content = request.content
    source_url = request.source_url
    context = request.context
    
    print(f"\n💾 Saving to Supermemory: {title}")
    
    try:
        # Format the content for storage
        memory_content = f"""# {title}

{content}
"""
        if source_url:
            memory_content += f"\n\n**Source:** {source_url}"
        
        if context:
            memory_content += f"\n\n**Context when found:** {context[:500]}..."
        
        # Add metadata
        metadata = {
            "source": "minnets_web_search",
            "source_url": source_url,
            "saved_at": datetime.now().isoformat()
        }
        
        # Save to Supermemory
        memory_id = await supermemory_client.add_memory(
            content=memory_content,
            metadata=metadata
        )
        
        if memory_id:
            print(f"   ✅ Saved with ID: {memory_id}")
            return {
                "status": "saved",
                "memory_id": memory_id,
                "title": title
            }
        else:
            print("   ❌ Failed to save")
            return {
                "status": "error",
                "message": "Failed to save to Supermemory"
            }
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return {
            "status": "error", 
            "message": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
