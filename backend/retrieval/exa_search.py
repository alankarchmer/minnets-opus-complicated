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
        use_autoprompt: bool = True,
        exclude_domains: list[str] = None,
        exclude_text: str = None
    ) -> list[SearchResult]:
        """
        Perform neural semantic search on the web.
        
        Args:
            query: The search query
            num_results: Number of results to return
            use_autoprompt: Let Exa optimize the query
            exclude_domains: List of domains to exclude (e.g., ["wikipedia.org"])
            exclude_text: Text that results should NOT primarily be about
            
        Returns:
            List of search results with content
        """
        try:
            # Build search parameters
            search_params = {
                "type": "neural",
                "num_results": num_results + 3,  # Fetch extra for filtering
                "text": {"max_characters": 2000},
                "use_autoprompt": use_autoprompt
            }
            
            # Add domain exclusions if provided
            if exclude_domains:
                search_params["exclude_domains"] = exclude_domains
            
            # Note: exa_py is sync, we run it in the event loop
            response = self.client.search_and_contents(
                query,
                **search_params
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
            
            # Filter out results that are primarily about the excluded text
            if exclude_text and results:
                results = self._filter_redundant_results(results, exclude_text)
            
            return results[:num_results]
            
        except Exception as e:
            print(f"Exa search error: {e}")
            return []
    
    def _filter_redundant_results(
        self, 
        results: list[SearchResult], 
        exclude_text: str
    ) -> list[SearchResult]:
        """
        Filter out results that are primarily about the same subject
        the user is already viewing.
        
        Uses simple heuristics - if the title or text heavily features
        the excluded subject, filter it out.
        """
        exclude_lower = exclude_text.lower()
        exclude_words = set(exclude_lower.split())
        
        filtered = []
        for result in results:
            title_lower = result.title.lower()
            text_preview = result.text[:500].lower()
            
            # Check if the title is primarily about the excluded subject
            title_match = exclude_lower in title_lower
            
            # Check if multiple words from excluded text appear in title
            title_words = set(title_lower.split())
            word_overlap = len(exclude_words & title_words)
            high_word_overlap = word_overlap >= min(2, len(exclude_words))
            
            # Check if the text starts with the excluded subject (likely a Wikipedia-style page)
            text_starts_with = text_preview.startswith(exclude_lower)
            
            # Filter if it seems to be primarily about the same thing
            is_redundant = (title_match or (high_word_overlap and text_starts_with))
            
            if not is_redundant:
                filtered.append(result)
            else:
                print(f"   🚫 Filtered redundant result: {result.title[:50]}")
        
        return filtered
    
    async def search_for_connections(
        self,
        concepts: list[str],
        main_subject: str = None,
        num_results: int = 5
    ) -> list[SearchResult]:
        """
        Search for content that CONNECTS to the concepts but is NOT about
        the main subject the user is already viewing.
        
        This is the key method for avoiding redundancy.
        """
        if not concepts:
            return []
        
        # Build a query that emphasizes the tangential concepts
        query = " ".join(concepts[:3])
        
        # Add context-setting prefix to guide semantic search
        # This helps find articles ABOUT the concepts, not just mentioning them
        enhanced_query = f"{query}"
        
        print(f"   🔍 Searching for connections: '{enhanced_query}'")
        if main_subject:
            print(f"   🚫 Excluding results about: '{main_subject}'")
        
        # Exclude common domains that might have duplicate content
        exclude_domains = []
        
        results = await self.search(
            query=enhanced_query,
            num_results=num_results,
            use_autoprompt=True,
            exclude_domains=exclude_domains,
            exclude_text=main_subject
        )
        
        return results
    
    async def find_similar(
        self,
        url: str,
        num_results: int = 5,
        exclude_same_domain: bool = True
    ) -> list[SearchResult]:
        """
        Find web pages similar to a given URL.
        Useful for finding related research papers, articles, etc.
        
        Args:
            url: URL to find similar content for
            num_results: Number of results
            exclude_same_domain: Whether to exclude results from same domain
        """
        try:
            params = {
                "num_results": num_results,
                "text": {"max_characters": 2000}
            }
            
            if exclude_same_domain:
                # Extract domain from URL and exclude it
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                if domain:
                    params["exclude_domains"] = [domain]
            
            response = self.client.find_similar_and_contents(
                url,
                **params
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
