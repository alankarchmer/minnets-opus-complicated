import os
from exa_py import Exa
from typing import Optional

from models import SearchResult
from config import get_settings


class ExaSearchClient:
    """Client for Exa.ai neural web search."""
    
    def __init__(self):
        settings = get_settings()
        self.client = Exa(api_key=settings.exa_api_key)
    
    async def search(
        self, 
        query: str, 
        num_results: int = 5,
        use_autoprompt: bool = True
    ) -> list[SearchResult]:
        """
        Perform neural semantic search on the web.
        
        Args:
            query: The search query
            num_results: Number of results to return
            use_autoprompt: Let Exa optimize the query
            
        Returns:
            List of search results with content
        """
        try:
            # Note: exa_py is sync, we run it in the event loop
            response = self.client.search_and_contents(
                query,
                type="neural",
                num_results=num_results,
                text={"max_characters": 2000},
                use_autoprompt=use_autoprompt
            )
            
            results = []
            for item in response.results:
                result = SearchResult(
                    title=item.title or "",
                    url=item.url,
                    text=item.text or "",
                    score=item.score if hasattr(item, 'score') else 0.8,
                    published_date=item.published_date if hasattr(item, 'published_date') else None
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Exa search error: {e}")
            return []
    
    async def find_similar(
        self,
        url: str,
        num_results: int = 5
    ) -> list[SearchResult]:
        """
        Find web pages similar to a given URL.
        Useful for finding related research papers, articles, etc.
        """
        try:
            response = self.client.find_similar_and_contents(
                url,
                num_results=num_results,
                text={"max_characters": 2000}
            )
            
            results = []
            for item in response.results:
                result = SearchResult(
                    title=item.title or "",
                    url=item.url,
                    text=item.text or "",
                    score=item.score if hasattr(item, 'score') else 0.8,
                    published_date=item.published_date if hasattr(item, 'published_date') else None
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Exa find_similar error: {e}")
            return []
    
    async def get_contents(
        self,
        urls: list[str]
    ) -> list[SearchResult]:
        """
        Fetch the content of specific URLs.
        Useful when we have a URL from the browser and need its content.
        """
        try:
            response = self.client.get_contents(
                urls,
                text={"max_characters": 8000}
            )
            
            results = []
            for item in response.results:
                result = SearchResult(
                    title=item.title or "",
                    url=item.url,
                    text=item.text or "",
                    score=1.0,  # Direct fetch, so full relevance
                    published_date=item.published_date if hasattr(item, 'published_date') else None
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Exa get_contents error: {e}")
            return []

