from openai import AsyncOpenAI
from typing import Union
import json
import uuid

from models import Memory, SearchResult, Suggestion, SuggestionSource
from config import get_settings


class OpenAISynthesizer:
    """
    Uses OpenAI GPT to:
    1. Extract key concepts from user's screen context
    2. Decide whether to use memory, web search, or both
    3. Synthesize retrieved content into human-readable suggestions
    """
    
    def __init__(self):
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def extract_concepts(self, context: str, app_name: str) -> list[str]:
        """
        Extract key concepts/topics from the user's screen context.
        These concepts drive the retrieval process.
        """
        system_prompt = """You are a concept extraction system. Given text from a user's screen, extract the 3-5 most important concepts, topics, or themes that would be useful for finding related information.

Focus on:
- Technical terms and concepts
- Named entities (tools, frameworks, people, companies)
- Key ideas or problems being discussed
- Domain-specific terminology

Return ONLY a JSON array of concept strings, nothing else.
Example: ["transformer architecture", "attention mechanism", "PyTorch", "GPU memory optimization"]"""

        user_prompt = f"""App: {app_name}

Screen Content:
{context[:4000]}"""  # Limit context size

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            # Parse JSON array
            concepts = json.loads(result)
            return concepts if isinstance(concepts, list) else []
            
        except Exception as e:
            print(f"Concept extraction error: {e}")
            # Fallback: extract simple keywords
            return self._fallback_extraction(context)
    
    def _fallback_extraction(self, context: str) -> list[str]:
        """Simple keyword extraction fallback."""
        # Very basic extraction - just get long words
        words = context.split()
        keywords = [w.strip(".,!?()[]{}:;\"'") for w in words if len(w) > 6]
        # Get unique keywords
        seen = set()
        unique = []
        for kw in keywords:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique.append(kw)
        return unique[:5]
    
    async def should_search_web(
        self, 
        context: str, 
        memory_results: list[Memory]
    ) -> bool:
        """
        Decide whether to supplement memory results with web search.
        
        Triggers for web search:
        - Few or no relevant memories found
        - Context mentions recent events, news, or unfamiliar terms
        - User appears to be learning something new
        """
        # Simple heuristics first
        if len(memory_results) < 2:
            return True
        
        avg_similarity = sum(m.similarity for m in memory_results) / len(memory_results)
        if avg_similarity < 0.7:
            return True
        
        # Use LLM for nuanced decision
        system_prompt = """You decide whether to search the web for additional context.

Return "true" if:
- The topic seems recent or time-sensitive
- The user might benefit from external sources
- The memory results seem incomplete

Return "false" if:
- The user's own knowledge seems sufficient
- The topic is personal or internal
- Memory results are comprehensive

Return ONLY "true" or "false", nothing else."""

        user_prompt = f"""Context (what user is viewing):
{context[:2000]}

Memory results found: {len(memory_results)}
Average relevance: {avg_similarity:.2f}
Top memories: {[m.content[:100] for m in memory_results[:3]]}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=10
            )
            
            result = response.choices[0].message.content.strip().lower()
            return result == "true"
            
        except Exception as e:
            print(f"Web search decision error: {e}")
            return len(memory_results) < 2
    
    async def synthesize_suggestion(
        self,
        item: Union[Memory, SearchResult],
        context: str,
        relevance_score: float,
        novelty_score: float
    ) -> Suggestion:
        """
        Create a deeply synthesized insight from a retrieved item.
        Extracts specific, actionable knowledge and connects it to user's context.
        """
        is_memory = isinstance(item, Memory)
        source = SuggestionSource.SUPERMEMORY if is_memory else SuggestionSource.WEB_SEARCH
        
        system_prompt = """You are a brilliant research assistant who synthesizes information into actionable insights.

Your job is to extract the MOST VALUABLE specific knowledge from a source and connect it directly to what the user is working on.

CRITICAL RULES:
1. Extract SPECIFIC facts, numbers, frameworks, or techniques - not vague summaries
2. Show exactly HOW this applies to the user's current work
3. Be concrete and actionable - what should they DO or CONSIDER?
4. Write like a smart colleague sharing a discovery, not a search engine describing a link

BAD examples (too vague):
- "This article discusses real estate investing strategies"
- "Consider reviewing this resource about cap rates"
- "This paper explores valuation methods"

GOOD examples (specific & actionable):
- "The 1% rule (monthly rent ≥ 1% of purchase price) can quickly filter your target properties. Your current cap rate analysis could incorporate this as a first-pass filter."
- "Research shows cap rates compress by 50-100bps in markets with >3% population growth. Cross-reference your target markets' demographics."
- "The paper finds that leverage above 75% LTV increases default probability 3x in downturns. Your thesis mentions using leverage - consider stress-testing at different LTV levels."

Return JSON:
{
    "title": "Action-oriented title that hints at the specific insight (max 60 chars)",
    "content": "2-4 sentences extracting the SPECIFIC valuable information and showing exactly how it applies to their current context. Include concrete numbers, frameworks, or techniques when available.",
    "reasoning": "One sentence explaining the direct connection to their work."
}"""

        if is_memory:
            item_description = f"""SOURCE (from your saved notes):
{item.content[:2000]}"""
        else:
            item_description = f"""SOURCE ({item.title}):
{item.text[:2000]}"""

        user_prompt = f"""WHAT THE USER IS CURRENTLY WORKING ON:
{context[:2500]}

---

{item_description}

---

Extract the most specific, actionable insight from this source that directly helps with what the user is working on. Be concrete - include specific numbers, frameworks, techniques, or facts when available."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            
            # Handle potential markdown code blocks in response
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            
            data = json.loads(result)
            
            # Get source URL for web results
            source_url = None
            if not is_memory and hasattr(item, 'url'):
                source_url = item.url
            
            return Suggestion(
                id=str(uuid.uuid4()),
                title=data.get("title", "Related insight")[:60],
                content=data.get("content", item.content if is_memory else item.text)[:600],
                reasoning=data.get("reasoning", "This connects to what you're currently viewing."),
                source=source,
                relevance_score=relevance_score,
                novelty_score=novelty_score,
                source_url=source_url
            )
            
        except Exception as e:
            print(f"Synthesis error: {e}")
            import traceback
            traceback.print_exc()
            
            # Get source URL for web results
            source_url = None
            if not is_memory and hasattr(item, 'url'):
                source_url = item.url
            
            # Fallback suggestion
            return Suggestion(
                id=str(uuid.uuid4()),
                title=item.content[:60] if is_memory else item.title[:60],
                content=item.content[:300] if is_memory else item.text[:300],
                reasoning="This information relates to your current context.",
                source=source,
                relevance_score=relevance_score,
                novelty_score=novelty_score,
                source_url=source_url
            )

