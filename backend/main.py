import asyncio
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import (
    AnalyzeRequest, 
    AnalyzeResponse, 
    Suggestion,
    SuggestionSource,
    Memory,
    SearchResult,
    SaveToMemoryRequest
)
from retrieval.exa_search import ExaSearchClient
from retrieval.supermemory import SupermemoryClient
from retrieval.scoring import RetrievalScorer
from retrieval.cascade_router import CascadeRouter, RetrievalPath, ConfidenceLevel
from synthesis.openai_client import OpenAISynthesizer
from config import get_settings


# Global instances
exa_client: ExaSearchClient = None
supermemory_client: SupermemoryClient = None
synthesizer: OpenAISynthesizer = None
scorer: RetrievalScorer = None
cascade_router: CascadeRouter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global exa_client, supermemory_client, synthesizer, scorer, cascade_router
    
    exa_client = ExaSearchClient()
    supermemory_client = SupermemoryClient()
    synthesizer = OpenAISynthesizer()
    scorer = RetrievalScorer()
    cascade_router = CascadeRouter()
    
    print("🧠 Minnets backend started")
    print("   Using CascadeRouter: Graph Pivot → Vector → Web")
    print("   Graph Pivot: Echo chamber filter + neighbor pivoting")
    print("   Using Exa.ai for web search (with redundancy filtering)")
    print("   Using Supermemory for knowledge base")
    print("   Using OpenAI for synthesis")
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
    Main analysis endpoint.
    
    Takes user's screen context and returns proactive suggestions.
    
    KEY INSIGHT: We search for TANGENTIAL concepts, not the main subject.
    If user is reading about Pep Guardiola, we search for "positional play",
    "gegenpressing comparison", "Johan Cruyff influence" - NOT Pep Guardiola.
    """
    start_time = time.time()
    
    print(f"\n📥 Analyzing context from: {request.app_name}")
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
        
        # Step 2: Also extract the main subject for redundancy filtering
        main_subject = await synthesizer.extract_for_redundancy_check(context)
        print(f"   🚫 Will filter out results about: '{main_subject}'")
        
        # Step 3: Search for CONNECTIONS, not the same thing
        # Use tangential concepts as query, filter out main subject
        search_query = " ".join(concepts[:3])
        print(f"   🔍 Searching for: '{search_query}'")
        
        # Try knowledge base first with cascade router
        cascade_result = await cascade_router.route(
            query=search_query,
            context=context
        )
        
        print(f"   Path: {cascade_result.path.value}, Confidence: {cascade_result.confidence.value}")
        
        # If low confidence from KB, supplement with web search for tangential concepts
        if cascade_result.confidence == ConfidenceLevel.LOW or not cascade_result.items:
            print(f"   📡 Searching web for tangential concepts...")
            web_results = await exa_client.search_for_connections(
                concepts=concepts,
                main_subject=main_subject,
                num_results=5
            )
            
            if web_results:
                print(f"   Found {len(web_results)} web results after redundancy filtering")
                cascade_result.items = web_results
                cascade_result.path = RetrievalPath.WEB
        
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
        
        # Step 4: Score and filter results
        scored_items = scorer.filter_and_rank(cascade_result.items, max_results=3)
        print(f"   Scored {len(scored_items)} results")
        
        # Step 5: Synthesize suggestions (emphasizing what's DIFFERENT)
        print("   Synthesizing suggestions (emphasizing novelty)...")
        suggestions = []
        
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


@app.post("/feedback")
async def record_feedback(
    suggestion_id: str,
    helpful: bool,
    action: str = None  # "dismissed", "saved", "clicked"
):
    """
    Record user feedback on suggestions.
    This can be used to improve retrieval over time.
    """
    # TODO: Implement feedback storage and learning
    return {"status": "recorded", "suggestion_id": suggestion_id}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
