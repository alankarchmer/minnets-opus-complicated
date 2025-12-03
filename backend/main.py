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
from synthesis.openai_client import OpenAISynthesizer
from config import get_settings


# Global instances
exa_client: ExaSearchClient = None
supermemory_client: SupermemoryClient = None
synthesizer: OpenAISynthesizer = None
scorer: RetrievalScorer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources."""
    global exa_client, supermemory_client, synthesizer, scorer
    
    exa_client = ExaSearchClient()
    supermemory_client = SupermemoryClient()
    synthesizer = OpenAISynthesizer()
    scorer = RetrievalScorer()
    
    print("🧠 Minnets backend started")
    print("   Using Exa.ai for web search")
    print("   Using Supermemory for knowledge base")
    print("   Using OpenAI for synthesis")
    yield
    
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
    Currently uses Exa.ai web search since no Supermemory KB is configured.
    """
    start_time = time.time()
    
    print(f"\n📥 Analyzing context from: {request.app_name}")
    print(f"   Context length: {len(request.context)} chars")
    
    context = request.context
    
    # Check if context contains a URL that we should fetch content for
    if "CURRENT_URL:" in context:
        try:
            url_line = [line for line in context.split("\n") if "CURRENT_URL:" in line][0]
            url = url_line.replace("CURRENT_URL:", "").strip()
            
            if url and not url.startswith("chrome://") and not url.startswith("about:"):
                print(f"   🌐 Fetching content from URL: {url}")
                
                # Use Exa to get the content of this specific URL
                url_content = await exa_client.get_contents([url])
                
                if url_content and len(url_content) > 0:
                    fetched = url_content[0]
                    context = f"Page Title: {fetched.title}\nURL: {url}\n\nContent:\n{fetched.text[:8000]}"
                    print(f"   ✓ Fetched {len(fetched.text)} chars from URL")
                else:
                    print(f"   ⚠️ Could not fetch URL content, using original context")
        except Exception as e:
            print(f"   ⚠️ Error fetching URL: {e}")
    
    try:
        # Step 1: Extract concepts from context
        print("   Extracting concepts...")
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
        
        print(f"   Concepts: {concepts}")
        
        # Step 2a: Search Supermemory for personal knowledge
        search_query = " ".join(concepts[:3])  # Use top 3 concepts
        print(f"   Searching Supermemory for: '{search_query}'")
        
        memory_results = await supermemory_client.search(search_query, limit=3)
        print(f"   Found {len(memory_results)} memories")
        
        # Step 2b: Search the web with Exa
        print(f"   Searching Exa for: '{search_query}'")
        
        web_results = await exa_client.search(search_query, num_results=5)
        print(f"   Found {len(web_results)} web results")
        
        # Combine results (memories first, then web)
        all_results = []
        
        # Convert memories to SearchResult format for scoring
        for mem in memory_results:
            from models import SearchResult
            all_results.append(SearchResult(
                title=f"From Your Memory",
                url="supermemory://local",
                text=mem.content,
                score=mem.similarity,
                published_date=mem.created_at.isoformat() if mem.created_at else None
            ))
        
        all_results.extend(web_results)
        
        if not all_results:
            print("   No results found from memory or web")
            return AnalyzeResponse(
                suggestions=[],
                processing_time_ms=int((time.time() - start_time) * 1000)
            )
        
        # Step 3: Score and filter results
        scored_items = scorer.filter_and_rank(all_results, max_results=3)
        print(f"   Scored {len(scored_items)} results")
        
        # Step 4: Synthesize suggestions
        print("   Synthesizing suggestions...")
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
        
        return AnalyzeResponse(
            suggestions=suggestions,
            processing_time_ms=processing_time
        )
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
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
