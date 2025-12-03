import os
from typing import Optional
from datetime import datetime

from models import Memory
from config import get_settings


class SupermemoryClient:
    """
    Client for interacting with Supermemory API using official SDK.
    
    Supermemory provides two types of search:
    - Memory Search (v4): For user context, preferences, and history (memories are extracted facts)
    - Document Search (v3): For raw documents, PDFs, etc.
    
    Also supports User Profiles which combine static facts + dynamic context.
    """
    
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.supermemory_api_key
        self.client = None
        
        # Only initialize if API key is configured
        if self.api_key and self.api_key != "your-supermemory-api-key":
            try:
                from supermemory import Supermemory
                self.client = Supermemory(api_key=self.api_key)
                print("   ✓ Supermemory client initialized")
            except ImportError:
                print("   ⚠️ Supermemory SDK not installed. Run: pip install supermemory")
            except Exception as e:
                print(f"   ⚠️ Supermemory init error: {e}")
        else:
            print("   ⚠️ Supermemory API key not configured")
    
    def _get_attr(self, obj, key: str, default=None):
        """
        Helper to get attribute from object or dict.
        SDK may return objects with attributes or dicts depending on version.
        """
        if hasattr(obj, key):
            return getattr(obj, key, default)
        elif isinstance(obj, dict):
            return obj.get(key, default)
        return default
    
    def _get_results(self, response) -> list:
        """Extract results list from response object or dict."""
        if hasattr(response, 'results'):
            return response.results or []
        elif isinstance(response, dict):
            return response.get("results", [])
        return []
    
    async def search(
        self, 
        query: str, 
        limit: int = 5, 
        container_tag: str = None,
        threshold: float = 0.5,
        include_related: bool = True
    ) -> list[Memory]:
        """
        Search memories using Supermemory's v4 memories search.
        Best for understanding user context, preferences, and history.
        
        Memories are extracted facts that:
        - Evolve in real time
        - Handle knowledge updates and temporal changes
        - Form relationships (extends, updates, derives)
        
        Args:
            query: The search query
            limit: Max number of results
            container_tag: Filter by container tag (user ID, project, etc.)
            threshold: Similarity threshold (0-1), lower = more results
            include_related: Whether to include parent/child memories
        """
        if not self.client:
            return []
        
        try:
            # Use memories search (v4) for conversational/contextual search
            params = {
                "q": query,
                "limit": limit,
                "threshold": threshold,
                "rerank": True
            }
            
            if container_tag:
                params["container_tag"] = container_tag
            
            # Include related memories and documents for richer context
            if include_related:
                params["include"] = {
                    "relatedMemories": True,
                    "documents": True
                }
            
            response = self.client.search.memories(**params)
            
            memories = []
            for item in self._get_results(response):
                memory = Memory(
                    id=self._get_attr(item, "id", ""),
                    content=self._get_attr(item, "memory", ""),
                    similarity=self._get_attr(item, "similarity", 0.0),
                    created_at=self._parse_date(self._get_attr(item, "updatedAt")),
                    last_accessed=None,
                    source_document_id=None,
                    relationships=[]
                )
                
                # Extract related memories from context (parents = what this extends/derives from)
                context = self._get_attr(item, "context", {})
                if context:
                    parents = self._get_attr(context, "parents", [])
                    if parents:
                        for parent in parents:
                            memory.relationships.append({
                                "type": self._get_attr(parent, "relation", "extends"),
                                "content": self._get_attr(parent, "memory", ""),
                                "version": self._get_attr(parent, "version")
                            })
                    
                    # Also track children (what derives from this)
                    children = self._get_attr(context, "children", [])
                    if children:
                        for child in children:
                            memory.relationships.append({
                                "type": f"child_{self._get_attr(child, 'relation', 'derives')}",
                                "content": self._get_attr(child, "memory", ""),
                                "version": self._get_attr(child, "version")
                            })
                
                # Link to source documents if available
                docs = self._get_attr(item, "documents", [])
                if docs and len(docs) > 0:
                    memory.source_document_id = self._get_attr(docs[0], "id")
                
                memories.append(memory)
            
            print(f"   Supermemory: Found {len(memories)} memories")
            return memories
            
        except Exception as e:
            print(f"   Supermemory search error: {e}")
            return []
    
    async def get_related(
        self, 
        anchor_id: str, 
        relationship_types: list[str] = None
    ) -> list[Memory]:
        """
        Get memories related to an anchor memory via graph relationships.
        
        In Supermemory, relationships are returned as part of the memory context.
        This method searches for the anchor and returns its related memories.
        
        Relationship types in Supermemory:
        - extends: New info adds to existing knowledge without replacing
        - updates: New info contradicts/updates existing knowledge  
        - derives: Inferred connections from patterns in knowledge
        
        Args:
            anchor_id: ID of the anchor memory
            relationship_types: Filter by relationship types (e.g., ["derives", "extends"])
        """
        if not self.client:
            return []
        
        if relationship_types is None:
            relationship_types = ["derives", "extends", "updates"]
        
        try:
            # Get the anchor memory with its context
            anchor = await self.get_memory(anchor_id)
            if not anchor:
                return []
            
            # Search for memories related to this anchor's content
            # Using the anchor content as query to find graph-connected memories
            related = await self.search(
                query=anchor.content[:500],  # Use first 500 chars as query
                limit=10,
                include_related=True,
                threshold=0.3  # Lower threshold to find more connections
            )
            
            # Filter to only include memories with matching relationship types
            result = []
            for mem in related:
                # Check if this memory has any of the requested relationships
                for rel in mem.relationships:
                    rel_type = rel.get("type", "").replace("child_", "")
                    if rel_type in relationship_types:
                        result.append(mem)
                        break
            
            return result
            
        except Exception as e:
            print(f"   Supermemory get_related error: {e}")
            return []
    
    async def get_profile(
        self, 
        container_tag: str, 
        query: str = None
    ) -> dict:
        """
        Get user profile with static facts + dynamic context + relevant memories.
        
        This is the recommended way to get context for LLM responses.
        Returns a combination of:
        - Static profile: Information the agent should always know
        - Dynamic profile: Episodic information from recent conversations
        - Search results: Relevant memories for the current query
        
        Args:
            container_tag: User ID or container to get profile for
            query: Optional query to get relevant memories alongside profile
        
        Returns:
            dict with 'profile' (static/dynamic lists) and 'search_results'
        """
        if not self.client:
            return {"profile": {"static": [], "dynamic": []}, "search_results": []}
        
        try:
            params = {"container_tag": container_tag}
            if query:
                params["q"] = query
            
            response = self.client.profile(**params)
            
            # Extract profile data
            profile_data = self._get_attr(response, "profile", {})
            static = self._get_attr(profile_data, "static", [])
            dynamic = self._get_attr(profile_data, "dynamic", [])
            
            # Extract search results if query was provided
            search_data = self._get_attr(response, "search_results", {})
            results = self._get_attr(search_data, "results", [])
            
            memories = []
            for item in results:
                memories.append(Memory(
                    id=self._get_attr(item, "id", ""),
                    content=self._get_attr(item, "content", ""),
                    similarity=self._get_attr(item, "similarity", 0.0),
                    created_at=self._parse_date(self._get_attr(item, "updatedAt")),
                    last_accessed=None,
                    source_document_id=None,
                    relationships=[]
                ))
            
            print(f"   Supermemory profile: {len(static)} static, {len(dynamic)} dynamic, {len(memories)} memories")
            
            return {
                "profile": {
                    "static": list(static) if not isinstance(static, list) else static,
                    "dynamic": list(dynamic) if not isinstance(dynamic, list) else dynamic
                },
                "search_results": memories
            }
            
        except Exception as e:
            print(f"   Supermemory get_profile error: {e}")
            return {"profile": {"static": [], "dynamic": []}, "search_results": []}
    
    async def search_documents(
        self, 
        query: str, 
        limit: int = 5, 
        container_tags: list[str] = None,
        rewrite_query: bool = False
    ) -> list[Memory]:
        """
        Search documents using Supermemory's v3 document search.
        Best for searching through uploaded documents, PDFs, etc.
        
        Use this for:
        - Legal/finance documents
        - Searching through Google Drive files
        - Chat with documentation
        
        Args:
            query: The search query
            limit: Max number of results
            container_tags: Filter by container tags (plural array for document search)
            rewrite_query: Expand query for better results (+400ms latency)
        """
        if not self.client:
            return []
        
        try:
            params = {
                "q": query,
                "limit": limit,
                "document_threshold": 0.5,
                "chunk_threshold": 0.6,
                "rerank": True,
                "include_summary": True,
                "rewrite_query": rewrite_query
            }
            
            if container_tags:
                params["container_tags"] = container_tags
            
            response = self.client.search.documents(**params)
            
            memories = []
            for doc in self._get_results(response):
                # Combine chunks into content
                chunks = self._get_attr(doc, "chunks", [])
                content_parts = []
                for c in chunks:
                    if self._get_attr(c, "isRelevant", True):
                        chunk_content = self._get_attr(c, "content", "")
                        if chunk_content:
                            content_parts.append(chunk_content)
                
                content = "\n\n".join(content_parts)
                
                memory = Memory(
                    id=self._get_attr(doc, "documentId", ""),
                    content=content or self._get_attr(doc, "title", ""),
                    similarity=self._get_attr(doc, "score", 0.0),
                    created_at=self._parse_date(self._get_attr(doc, "createdAt")),
                    last_accessed=self._parse_date(self._get_attr(doc, "updatedAt")),
                    source_document_id=self._get_attr(doc, "documentId"),
                    relationships=[]
                )
                memories.append(memory)
            
            print(f"   Supermemory: Found {len(memories)} documents")
            return memories
            
        except Exception as e:
            print(f"   Supermemory document search error: {e}")
            return []
    
    async def add_memory(
        self, 
        content: str, 
        metadata: dict = None, 
        container_tag: str = "minnets",
        custom_id: str = None
    ) -> Optional[str]:
        """
        Add content to Supermemory. 
        Content is processed into searchable memories automatically.
        
        Supermemory will:
        - Extract memories from the content
        - Build/update user profiles
        - Create relationships between memories
        
        Args:
            content: Text, URL, or other content to add
            metadata: Key-value metadata (strings, numbers, booleans only)
            container_tag: Tag for grouping (e.g., user ID) - singular for performance
            custom_id: Your own ID for deduplication and updates
        
        Returns:
            Document ID if successful, None otherwise
        """
        if not self.client:
            print("   ⚠️ Cannot add memory: Supermemory client not initialized")
            return None
        
        try:
            params = {
                "content": content,
                "container_tag": container_tag,
                "metadata": metadata or {}
            }
            
            if custom_id:
                params["custom_id"] = custom_id
            
            result = self.client.memories.add(**params)
            
            memory_id = self._get_attr(result, "id")
            status = self._get_attr(result, "status")
            
            print(f"   ✓ Added to Supermemory: {memory_id} (status: {status})")
            return memory_id
            
        except Exception as e:
            print(f"   Supermemory add_memory error: {e}")
            return None
    
    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        """Get a specific memory/document by ID."""
        if not self.client:
            return None
        
        try:
            result = self.client.memories.get(memory_id)
            
            return Memory(
                id=self._get_attr(result, "id", ""),
                content=self._get_attr(result, "content", ""),
                similarity=1.0,
                created_at=self._parse_date(self._get_attr(result, "createdAt")),
                last_accessed=self._parse_date(self._get_attr(result, "updatedAt")),
                source_document_id=memory_id,
                relationships=[]
            )
            
        except Exception as e:
            print(f"   Supermemory get_memory error: {e}")
            return None
    
    async def list_memories(
        self, 
        container_tags: list[str] = None,
        limit: int = 50,
        page: int = 1
    ) -> tuple[list[Memory], dict]:
        """
        List memories with pagination.
        
        Args:
            container_tags: Filter by tags
            limit: Items per page (max 200 recommended)
            page: Page number (1-indexed)
        
        Returns:
            Tuple of (memories list, pagination info)
        """
        if not self.client:
            return [], {}
        
        try:
            params = {
                "limit": limit,
                "page": page
            }
            
            if container_tags:
                params["container_tags"] = container_tags
            
            response = self.client.memories.list(**params)
            
            memories_data = self._get_attr(response, "memories", [])
            pagination = self._get_attr(response, "pagination", {})
            
            memories = []
            for item in memories_data:
                memories.append(Memory(
                    id=self._get_attr(item, "id", ""),
                    content=self._get_attr(item, "title", "") or self._get_attr(item, "summary", ""),
                    similarity=1.0,
                    created_at=self._parse_date(self._get_attr(item, "createdAt")),
                    last_accessed=self._parse_date(self._get_attr(item, "updatedAt")),
                    source_document_id=self._get_attr(item, "id"),
                    relationships=[]
                ))
            
            return memories, {
                "current_page": self._get_attr(pagination, "currentPage", page),
                "total_pages": self._get_attr(pagination, "totalPages", 1),
                "total_items": self._get_attr(pagination, "totalItems", len(memories)),
                "limit": self._get_attr(pagination, "limit", limit)
            }
            
        except Exception as e:
            print(f"   Supermemory list_memories error: {e}")
            return [], {}
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO date string to datetime."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return None
    
    async def close(self):
        """Close the client (no-op for SDK, kept for compatibility)."""
        pass
