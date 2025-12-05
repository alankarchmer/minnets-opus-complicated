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
        Extract RELATED concepts from the user's screen context.
        
        KEY INSIGHT: We want to find things that CONNECT to or EXPAND ON what 
        the user is viewing, NOT the exact same thing.
        
        For example, if user is on Pep Guardiola's Wikipedia page:
        - BAD: ["Pep Guardiola", "Manchester City", "football manager"]
        - GOOD: ["positional play tactics", "tiki-taka football philosophy", 
                 "Johan Cruyff influence on modern football", "elite coaching methodologies"]
        """
        system_prompt = """You are a serendipity engine that helps users discover RELATED but DIFFERENT information.

Given text from a user's screen, identify:
1. THE MAIN SUBJECT: What is this page/content primarily about? (person, topic, concept)
2. TANGENTIAL CONCEPTS: What related topics would ADD VALUE? Think:
   - Historical influences or predecessors
   - Comparable people/things in other domains
   - Underlying theories or methodologies
   - Contrasting perspectives or rivals
   - Deeper technical concepts mentioned
   - Related fields or applications

CRITICAL RULES:
- DO NOT return the main subject itself - the user already has that information!
- Return concepts that would EXPAND their understanding, not repeat it
- Think "if they're interested in X, they'd probably love to learn about Y"
- Be specific - "positional play football tactics" not just "football"

EXAMPLES:

User reading about: Pep Guardiola Wikipedia page
BAD output: ["Pep Guardiola", "Manchester City", "football manager"] 
GOOD output: ["positional play tactical philosophy", "Johan Cruyff total football legacy", "high pressing gegenpressing comparison", "Marcelo Bielsa influence on modern tactics"]

User reading about: Tesla stock analysis
BAD output: ["Tesla", "Elon Musk", "electric vehicles"]
GOOD output: ["battery technology cost curves", "BYD competitive analysis", "EV adoption S-curve dynamics", "manufacturing vertical integration strategy"]

User reading about: React documentation
BAD output: ["React", "JavaScript", "components"]
GOOD output: ["virtual DOM reconciliation algorithm", "Vue composition API comparison", "state management architectural patterns", "server components streaming benefits"]

Return JSON with two fields:
{
    "main_subject": "Brief description of what the page is primarily about",
    "tangential_concepts": ["concept1", "concept2", "concept3", "concept4"]
}"""

        user_prompt = f"""App: {app_name}

Screen Content:
{context[:4000]}

Identify the main subject (DO NOT search for this) and 4-5 tangential concepts that would add value to someone reading this."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,  # Higher temperature for more creative connections
                max_tokens=300
            )
            
            result = response.choices[0].message.content.strip()
            
            # Handle potential markdown code blocks
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
            
            data = json.loads(result)
            
            main_subject = data.get("main_subject", "")
            tangential = data.get("tangential_concepts", [])
            
            print(f"   📌 Main subject (excluded): {main_subject}")
            print(f"   🔗 Tangential concepts: {tangential}")
            
            return tangential if isinstance(tangential, list) else []
            
        except Exception as e:
            print(f"Concept extraction error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: extract simple keywords
            return self._fallback_extraction(context)
    
    async def extract_for_redundancy_check(self, context: str) -> str:
        """
        Extract the main subject from context for redundancy filtering.
        Used to filter out search results that are about the same thing.
        """
        system_prompt = """Extract the PRIMARY SUBJECT of this content in 2-5 words.

Examples:
- Wikipedia page about Elon Musk → "Elon Musk"
- Article about React hooks → "React hooks"
- Blog post about climate change → "climate change"

Return ONLY the subject, nothing else."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context[:2000]}
                ],
                temperature=0.1,
                max_tokens=20
            )
            
            return response.choices[0].message.content.strip().lower()
            
        except Exception as e:
            print(f"Main subject extraction error: {e}")
            return ""
    
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
2. Show exactly HOW this applies to the user's current interest
3. Be concrete and actionable - what should they DO or CONSIDER?
4. Write like a smart colleague sharing a discovery, not a search engine describing a link
5. EMPHASIZE what's DIFFERENT or ADDITIVE compared to what they're already reading

BAD examples (too vague or redundant):
- "This article discusses real estate investing strategies"
- "Here's more information about the same topic you're reading"
- "This paper explores valuation methods"

GOOD examples (specific, additive & actionable):
- "The 1% rule (monthly rent ≥ 1% of purchase price) can quickly filter properties. This framework could complement the cap rate analysis you're reviewing."
- "Klopp's gegenpressing recovers the ball within 8 seconds on average - a stark contrast to the patient buildup play described in your reading."
- "Research shows cap rates compress by 50-100bps in markets with >3% population growth. Cross-reference your target markets' demographics."

Return JSON:
{
    "title": "Action-oriented title that hints at the specific insight (max 60 chars)",
    "content": "2-4 sentences extracting the SPECIFIC valuable information and showing exactly how it ADDS TO or CONTRASTS WITH their current context. Include concrete numbers, frameworks, or techniques when available.",
    "reasoning": "One sentence explaining what NEW perspective this brings."
}"""

        if is_memory:
            item_description = f"""SOURCE (from your saved notes):
{item.content[:2000]}"""
        else:
            item_description = f"""SOURCE ({item.title}):
{item.text[:2000]}"""

        user_prompt = f"""WHAT THE USER IS CURRENTLY READING/VIEWING:
{context[:2500]}

---

{item_description}

---

Extract the most specific insight from this source that ADDS something new to what the user is viewing. Emphasize what's different, contrasting, or complementary - not redundant."""

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
