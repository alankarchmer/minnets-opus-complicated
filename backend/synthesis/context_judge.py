"""
Context Judge: LLM-based cognitive state analyzer for dynamic RAG routing.

Analyzes user's screen context and determines optimal retrieval strategy weights.
Uses continuous 0.0-1.0 weights for allocation-based routing (not binary gating).
"""

from openai import AsyncOpenAI
from models import StrategyWeights
from config import get_settings


JUDGE_SYSTEM_PROMPT = """You are the Cognitive State Analyzer for an AI OS.
Determine the user's INTENT (Serendipity/Relevance) and required INFORMATION SOURCE (Web/Local).

SCORING GUIDE (0.0 to 1.0):

Serendipity (need for novelty/unexpected connections):
  0.1: Coding, debugging, financial analysis (zero distraction allowed)
  0.3: Focused writing, specific research task
  0.5: Reading an article, casual writing (open to related ideas)
  0.7: Exploring a topic, learning something new
  0.9: Doomscrolling, bored, "stuck" on blank page (needs radical inspiration)

Relevance (need for precision/accuracy):
  0.1: Browsing for fun, looking for novelty
  0.3: Casual exploration, entertainment
  0.5: General reading, moderate accuracy needed
  0.7: Work task, need accurate information
  0.9: Specific factual query, debugging, hunting for a document

Source Web (external/fresh world knowledge):
  0.1: Personal journaling, reading own notes
  0.3: Working on internal project docs
  0.5: Balanced need for external and internal
  0.7: Learning new topic, need external references
  0.9: "Latest news", API docs, restaurant reviews, current events

Source Local (user's own memories/notes/history):
  0.1: Exploring completely new topic
  0.3: General browsing, unlikely to have notes
  0.5: Might have relevant past notes
  0.7: Working in familiar domain, likely have notes
  0.9: "My journal", project roadmap, past research, email drafts

HEURISTICS BY CONTEXT:
- Social Media scrolling → Serendipity: 0.8, Relevance: 0.2, Web: 0.7, Local: 0.3
- Coding/Debugging → Serendipity: 0.1, Relevance: 0.9, Web: 0.8, Local: 0.4
- Writing a Memoir → Serendipity: 0.3, Relevance: 0.7, Web: 0.2, Local: 0.9
- Blank page/stuck → Serendipity: 0.9, Relevance: 0.3, Web: 0.4, Local: 0.8
- Reading Wikipedia → Serendipity: 0.5, Relevance: 0.6, Web: 0.7, Local: 0.5
- Technical docs → Serendipity: 0.2, Relevance: 0.8, Web: 0.9, Local: 0.3
- Personal notes → Serendipity: 0.4, Relevance: 0.6, Web: 0.3, Local: 0.9

Provide precise float values (e.g., 0.75, not just 0.8).
Keep reasoning brief (1-2 sentences)."""


class ContextJudge:
    """
    Analyzes user context and determines optimal retrieval strategy weights.
    
    Uses OpenAI's structured output to ensure valid StrategyWeights response.
    Falls back to balanced defaults on error.
    """
    
    def __init__(self, client: AsyncOpenAI = None):
        settings = get_settings()
        self.client = client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.context_judge_model
    
    async def analyze(
        self, 
        context: str, 
        app_name: str, 
        window_title: str
    ) -> StrategyWeights:
        """
        Analyze context and return strategy weights.
        
        Args:
            context: Screen content text
            app_name: Name of the active application
            window_title: Title of the active window
            
        Returns:
            StrategyWeights with continuous 0.0-1.0 values
        """
        # Truncate context for speed (LLM doesn't need full page)
        context_summary = context[:1000] if len(context) > 1000 else context
        
        user_message = f"""Analyze this user context:

App: {app_name}
Window: {window_title}

Screen Content:
{context_summary}

Determine the optimal retrieval strategy weights."""

        try:
            completion = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                response_format=StrategyWeights,
                temperature=0.0  # We want consistent, reproducible logic
            )
            
            weights = completion.choices[0].message.parsed
            
            print(f"   🧠 Context Judge:")
            print(f"      Serendipity: {weights.serendipity:.2f}, Relevance: {weights.relevance:.2f}")
            print(f"      Web: {weights.source_web:.2f}, Local: {weights.source_local:.2f}")
            print(f"      Reasoning: {weights.reasoning[:80]}...")
            
            return weights
            
        except Exception as e:
            print(f"   ⚠️ Context Judge failed: {e}. Using balanced fallback.")
            return self._fallback_weights(app_name)
    
    def _fallback_weights(self, app_name: str) -> StrategyWeights:
        """
        Return reasonable fallback weights based on app name heuristics.
        Used when LLM call fails.
        """
        app_lower = app_name.lower()
        
        # Code editors -> high relevance, high web (docs)
        if any(x in app_lower for x in ["code", "xcode", "terminal", "iterm"]):
            return StrategyWeights(
                serendipity=0.15,
                relevance=0.85,
                source_web=0.75,
                source_local=0.35,
                reasoning="Fallback: Detected coding environment"
            )
        
        # Browsers -> balanced, slightly more web
        if any(x in app_lower for x in ["safari", "chrome", "firefox", "arc"]):
            return StrategyWeights(
                serendipity=0.45,
                relevance=0.55,
                source_web=0.65,
                source_local=0.45,
                reasoning="Fallback: Detected browser"
            )
        
        # Note apps -> high relevance, high local
        if any(x in app_lower for x in ["notes", "obsidian", "notion", "bear"]):
            return StrategyWeights(
                serendipity=0.35,
                relevance=0.65,
                source_web=0.25,
                source_local=0.85,
                reasoning="Fallback: Detected note-taking app"
            )
        
        # Default balanced
        return StrategyWeights(
            serendipity=0.4,
            relevance=0.6,
            source_web=0.5,
            source_local=0.5,
            reasoning="Fallback: Default balanced weights"
        )
