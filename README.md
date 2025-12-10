# Minnets

**Proactive Knowledge Companion for macOS**

Minnets watches what you're doing and surfaces relevant insights from your personal knowledge base (Supermemory) and the web (Exa.ai). Unlike chat interfaces, Minnets proactively suggests information - you don't need to know what to ask.

## Key Features

- **Proactive Suggestions**: No prompting required - insights appear when relevant
- **Context Judge**: LLM-based cognitive state analyzer determines optimal retrieval strategy
- **Orthogonal Search**: 6 strategies for cross-domain serendipity (noise injection, archetype bridge, cross-domain, PCA, antonym steering, cross-modal bridge)
- **Vector Math**: True embedding arithmetic for serendipitous discovery
- **Vibe Extraction**: Extracts emotional signatures and archetypes to enable cross-domain matching
- **Graph Pivot Retrieval**: Finds *connected but different* content, not just similar text
- **Smart Interruptibility**: 3-layer system prevents annoying you during flow states
- **Implicit Learning**: Learns your preferences from hover, expand, copy, dismiss signals
- **Training Data Collection**: Logs decisions and feedback for future model fine-tuning
- **Shadow Mode**: Cold-start learning without interrupting you

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     INTERRUPTIBILITY SYSTEM                      │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│  │ Flow Gate   │→ │ Confusion       │→ │ Contextual Bandit    │ │
│  │ (Hard Block)│  │ Detector        │  │ (Personalization)    │ │
│  └─────────────┘  └─────────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Swift/SwiftUI  │────▶│  Python Backend  │────▶│  Supermemory    │
│  (Menubar App)  │◀────│  (Local Server)  │◀────│  (Graph + RAG)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                       │
        │         ┌─────────────┼─────────────┐
        │         ▼             ▼             ▼
        │  ┌────────────┐ ┌───────────┐ ┌──────────────────┐
        │  │  Context   │ │ OpenAI +  │ │ Orthogonal Search│
        │  │  Judge     │ │ Exa       │ │ (6 Strategies)   │
        │  │  (LLM)     │ │ (Synth)   │ │                  │
        │  └─────┬──────┘ └───────────┘ └────────┬─────────┘
        │        │                               │
        │        ▼                       ┌───────┴───────┐
        │  ┌────────────┐               ▼               ▼
        │  │ Strategy   │        ┌────────────┐  ┌────────────┐
        │  │ Weights    │        │ Vector Math│  │ LLM-Based  │
        │  │ (4-dim)    │        │ (PCA, etc) │  │ (Vibe,etc) │
        │  └────────────┘        └────────────┘  └────────────┘
        ▼
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Floating Panel │────▶│ Implicit Feedback│────▶│ Judge Logger     │
│  (Suggestions)  │     │ Tracker          │     │ (Training Data)  │
└─────────────────┘     └──────────────────┘     └──────────────────┘
```

## The Interruptibility System

### Layer 1: Flow State Gate (Hard Rules)
Prevents catastrophic annoyance:
- **High-velocity typing** (>50 chars/min) → blocked
- **Presentation mode** (Keynote/PowerPoint fullscreen) → blocked  
- **Blacklisted apps** (Zoom, Discord calls, banking apps) → blocked

### Layer 2: Confusion Detector (Heuristics)
Identifies moments of need:
- **Thrashing**: Alt-tabbing IDE↔Browser 3+ times in 15 seconds
- **The Stare**: Mouse idle 5+ seconds while viewing content
- **Error Rate**: High backspace ratio (frustration signal)

### Layer 3: Contextual Bandit (Personalization)
Learns that:
- User A likes suggestions when reading PDFs
- User B prefers suggestions only when coding
- Time-of-day preferences, app-specific preferences, etc.

## The Retrieval Strategy

Traditional RAG shows you what's most similar to your context - but that's often redundant. Minnets uses a cascade architecture with **orthogonal search** and tangential concept extraction:

### Concept Extraction
- Extracts **tangential concepts** (related but different topics)
- Avoids searching for the main subject (user already has that)
- Example: Reading about "Pep Guardiola" → search for "positional play tactics", not "Pep Guardiola"

### Context Judge (Cognitive State Analyzer)

Before searching, Minnets analyzes your cognitive state using an LLM to determine optimal strategy weights:

```
┌─────────────────────────────────────────────────────────────────┐
│                      STRATEGY WEIGHTS (0.0 - 1.0)                │
│                                                                  │
│  INTENT DIMENSIONS:              SOURCE DIMENSIONS:              │
│  ├─ Serendipity: Need for       ├─ Web: Need for external,      │
│  │  novelty, surprises          │  fresh knowledge (Exa)        │
│  └─ Relevance: Need for         └─ Local: Need for personal     │
│     precision, accuracy            memories (Supermemory)        │
└─────────────────────────────────────────────────────────────────┘
```

**Context-based heuristics:**
| Context | Serendipity | Relevance | Web | Local |
|---------|-------------|-----------|-----|-------|
| Doomscrolling/bored | 0.9 | 0.2 | 0.7 | 0.3 |
| Coding/debugging | 0.1 | 0.9 | 0.8 | 0.4 |
| Writing a memoir | 0.3 | 0.7 | 0.2 | 0.9 |
| Blank page/stuck | 0.9 | 0.3 | 0.4 | 0.8 |
| Reading Wikipedia | 0.5 | 0.6 | 0.7 | 0.5 |

### Orthogonal Search (Serendipity Engine)

The key insight: **Standard search finds content ABOUT the same topic. Orthogonal search finds content that would delight the same TYPE OF PERSON.**

**Six strategies for "tangential leaps":**

#### LLM-Based Strategies (Original 3):

1. **Vector Noise Injection**: Perturb queries to land in adjacent semantic clusters
   - Adds controlled semantic "noise" to explore nearby but different concepts
   - Like taking a random walk from your query

2. **Archetype Bridge Search**: Map user vibes → archetype → what else that archetype loves
   - User reading about wabi-sabi pottery
   - System identifies: "People who value wabi-sabi seek 'un-designed' experiences"
   - Searches for: restaurants, music, architecture with same vibe

3. **Cross-Domain Vibe Search**: Project emotional signatures into different categories
   - Extract vibe: `["imperfect", "quiet", "handcrafted", "humble"]`
   - Archetype: "Someone who distrusts anything too polished or marketed"
   - Search in: restaurants, music, films, architecture, etc.

#### Vector Math Strategies (New 3 - True Embedding Arithmetic):

4. **Principal Component Subtraction (PCA)**: Remove dominant taste to reveal hidden preferences
   ```
   Q_serendipity = V_user - λ * proj_Vdom(V_user)
   ```
   - If user loves "Cyberpunk Anime", "Cyberpunk Novels", "Cyberpunk Games"
   - Standard search sees "Cyberpunk" as dominant
   - PCA subtracts it, revealing hidden preferences like "Neon Aesthetics"

5. **Antonym Steering**: Steer AWAY from current context, TOWARDS target vibe
   ```
   Q = V_taste + α * (V_target_vibe - V_current_context)
   ```
   - Unlike pure negation (-1 × V_context) which produces noise
   - This steers TOWARDS something: "relaxation", "novelty", "adventure"
   - Example: Sterile office → cozy cafe with mismatched furniture

6. **Cross-Modal Bridge**: Transform content from one domain to another
   ```
   Q = V_content + V_bridge  (where V_bridge = V_domain1 - V_domain2)
   ```
   - "If this movie were a restaurant, what would it be?"
   - Uses pre-computed domain transformation vectors

**Example:**
- User reading about: Wabi-sabi pottery
- Standard search finds: Japanese ceramics, pottery techniques
- Orthogonal search finds: Georgian restaurant with no website and handwritten menu (same vibe: humble, authentic, discovered-not-advertised)

### Cascade Router (Weighted Multi-Strategy)

The router uses **allocation-based routing** (not binary gating). Strategy weights determine:
- **HOW MANY** results to fetch from each source
- **HOW MUCH** to boost scores during ranking

```
┌────────────────────────────────────────────────────────────────┐
│  WEIGHTED ROUTING FLOW                                         │
│                                                                │
│  Context Judge → StrategyWeights → Parallel Fetch → Rerank    │
│                                                                │
│  Fetch Budget:                                                 │
│  ├─ Web:   max(1, 10 × source_web)   results from Exa         │
│  ├─ Local: max(1, 10 × source_local) results from Supermemory │
│  └─ Orthogonal: if serendipity > 0.2, run all 6 strategies    │
│                                                                │
│  Score Boosting:                                               │
│  ├─ Web results:        score × (1 + source_web)              │
│  ├─ Local results:      score × (1 + source_local)            │
│  └─ Orthogonal results: score × (1 + serendipity × 2.0)       │
└────────────────────────────────────────────────────────────────┘
```

**Available Retrieval Paths:**

0. **Orthogonal** (Serendipity): Cross-domain discovery
   - Run when `serendipity > 0.2`
   - All 6 strategies in parallel
   - Results reranked by cosine similarity to mathematical target vectors

1. **Graph Pivot**: Find graph-connected insights
   - Find anchors via vector search
   - Filter echo chamber (>85% similarity → pivot to neighbors)
   - Keep sweet spot anchors (65-85% similarity)
   - Traverse graph relationships (derives, extends, contrast)

2. **Vector**: Direct similarity search
   - High confidence (>85%) → Show KB results
   - Medium (65-85%) → Show KB + offer web search
   - Low (<65%) → Trigger web search

3. **Web**: When local knowledge is insufficient
   - Search for tangential concepts
   - Filter out results about main subject (redundancy avoidance)

4. **Weighted** (Default): Dynamic multi-strategy
   - Combines all sources based on Context Judge weights
   - Most flexible, adapts to cognitive state

### Scoring
- **MMR Doughnut**: Sweet spot is 65-85% similarity - related but novel
- **Temporal Boost**: Older, unaccessed memories get priority

## Setup

### Prerequisites

- macOS 14.0+
- Python 3.11+
- Xcode 15+
- API keys for:
  - [OpenAI](https://platform.openai.com/api-keys) (GPT-4.1)
  - [Supermemory](https://supermemory.ai) (knowledge base)
  - [Exa.ai](https://exa.ai) (web search)

### Backend Setup

```bash
cd backend

# Option 1: Use the startup script (recommended)
cp env.template .env
# Edit .env with your API keys
./run.sh

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.template .env
# Edit .env with your API keys
python main.py
```

The backend runs at `http://127.0.0.1:8000`. API docs at `http://127.0.0.1:8000/docs`.

### macOS App Setup

```bash
cd MinnetsMac

# Open in Xcode
open MinnetsMac.xcodeproj

# Build and run (⌘R)
```

**Important**: Grant permissions when prompted:
- **Accessibility**: Allows Minnets to read text from your screen
- **Screen Recording**: Fallback for apps that don't support Accessibility API

## Usage

1. **Launch**: Minnets appears as a brain icon in your menubar
2. **Toggle**: Click the icon or press `⌘⇧M` to show/hide the panel
3. **Suggestions**: As you work, Minnets will surface relevant insights
4. **Actions**:
   - **Why this?** - See why a suggestion is relevant
   - **Copy** - Copy the insight to clipboard
   - **Save** - Add to your Supermemory

## How It Works

### Context Capture

Minnets captures text from your frontmost window using a three-tier approach:
1. **AppleScript** (primary) - Extracts text and URLs from browsers (Chrome, Safari, Arc)
2. **Accessibility API** (fallback) - Direct text extraction when AppleScript fails
3. **ScreenCaptureKit + OCR** (last resort) - Screen capture + Vision framework OCR

For browsers, Minnets extracts the current URL and optionally fetches full page content via Exa.ai for richer context.

Captures happen every 15 seconds when context changes significantly.

### Retrieval Pipeline

The retrieval pipeline uses a **weighted multi-strategy architecture** with Context Judge and orthogonal search:

```python
# 1. Context Judge: Analyze cognitive state
weights = context_judge.analyze(screen_text, app_name, window_title)
# Returns StrategyWeights:
#   serendipity: 0.7  (need for novelty)
#   relevance:   0.3  (need for precision)
#   source_web:  0.6  (need for external knowledge)
#   source_local: 0.4 (need for personal memories)
#   reasoning: "User appears to be browsing casually..."

# 2. Extract TANGENTIAL concepts (not the main subject)
# If user is reading about "Pep Guardiola", extract:
# ["positional play tactics", "tiki-taka philosophy", "Johan Cruyff influence"]
# NOT ["Pep Guardiola", "Manchester City"]
concepts = extract_tangential_concepts(screen_text)

# 3. Weighted Routing: Parallel fetch based on weights
search_query = " ".join(concepts[:3])
cascade_result = cascade_router.route_weighted(
    query=search_query,
    context=screen_text,
    weights=weights
)

# Internally, this does:
#
# A. Budget Allocation:
#    limit_web = max(1, int(10 * weights.source_web))     # e.g., 6
#    limit_local = max(1, int(10 * weights.source_local)) # e.g., 4
#
# B. Parallel Strategy Dispatch:
#    if weights.serendipity > 0.2:
#        orthogonal_results = await orthogonal.search_all_strategies(...)
#        # Runs all 6 strategies: noise, archetype, cross-domain, PCA, antonym, bridge
#    
#    local_results = await supermemory.search(query, limit=limit_local)
#    web_results = await exa.search(query, limit=limit_web)
#
# C. Weighted Reranking:
#    for candidate in all_results:
#        if candidate.source == "web":
#            score *= (1 + weights.source_web)
#        if candidate.strategy == "orthogonal":
#            score *= (1 + weights.serendipity * 2.0)  # Heavy boost for serendipity

# 4. Score with MMR doughnut model
scored = apply_mmr_scoring(cascade_result.items)
# - Echo chamber (>0.85): Penalize 50%
# - Sweet spot (0.65-0.85): Bonus 20%
# - Too distant (<0.65): Lower score

# 5. Temporal boost for forgotten memories
scored = apply_temporal_boost(scored)  # log(days_since_accessed)

# 6. Synthesize human-readable suggestions
suggestions = synthesize(scored, context, emphasize_novelty=True)

# 7. Log decision for training
judge_logger.log_decision(
    request_id=request_id,
    weights=weights,
    insight_ids=[s.id for s in suggestions],
    retrieval_path=cascade_result.path
)
```

**Key Insight**: Minnets uses allocation-based routing (not binary gating). The Context Judge determines HOW MUCH of each strategy to use, not whether to use it at all.

### Scoring Model

**MMR Doughnut**:
- `> 0.85` (Hole): Echo chamber - penalize 50%
- `0.65 - 0.85` (Doughnut): Sweet spot - bonus 20%
- `< 0.65` (Air): Too distant - drop

**Temporal Novelty**:
```
score_final = score_vector × (1 + log(days_since_last_read))
```

## Implicit Feedback System

Instead of asking users to rate suggestions, Minnets tracks implicit signals:

| User Action | Implied Feedback | Reward |
|-------------|-----------------|--------|
| Immediate Dismiss (<1s) | "You annoyed me" | -5.0 |
| Dismiss (1-3s) | "Not relevant" | -1.0 |
| Ignore (Timeout) | "Didn't see/care" | -0.5 |
| Hover (2s+) | "Curious" | +1.0 |
| Expand "Why this?" | "Useful" | +2.0 |
| Copy Text | "Highly valuable" | +5.0 |
| Save to Memory | "Highly valuable" | +5.0 |

### Feedback Types

The backend supports both implicit and explicit feedback signals via `/feedback`:

```python
class FeedbackType(Enum):
    # Implicit signals
    CLICK = "click"
    DWELL = "dwell"
    DISMISS = "dismiss"
    SCROLL_PAST = "scroll_past"
    # Explicit signals
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    SAVE = "save"
```

### Training Data Collection

All decisions and feedback are logged to JSONL for future model training:

```jsonl
{"type": "decision", "request_id": "abc", "weights": {...}, "retrieval_path": "weighted", ...}
{"type": "feedback", "request_id": "abc", "insight_id": "xyz", "signal": "click", "dwell_time_ms": 5000}
```

This enables:
1. Evaluating which context types → which weights → positive outcomes
2. Training personalized models per user
3. Fine-tuning the Context Judge prompts

### Shadow Mode (Cold Start)

For the first 50 interactions, Minnets runs in "Shadow Mode":
- Generates suggestions but **doesn't show them**
- If you manually search for something it would have suggested → massive positive signal
- Calibrates the model without any annoyance

## Testing Mode (Current Configuration)

⚠️ **The interruptibility system is currently relaxed for testing.**

By default, the strict interruptibility gates would block most proactive suggestions:
- Confusion detection required (thrashing, staring, or high error rate)
- Shadow mode hides suggestions for first 50 interactions

**Current testing configuration:**
- Proactive suggestions show every 30 seconds without requiring confusion signals
- Shadow mode is disabled - suggestions display immediately
- Only Layer 1 (FlowStateGate) still blocks during Zoom/Teams, fast typing, or presentations

### Restoring Production Behavior

Search for `TODO: Restore` in the codebase to find the three locations to change:

1. **InterruptibilityManager.swift** - Restore confusion requirement:
   ```swift
   // Change from: always return shouldInterrupt: true
   // Back to: require confusion OR bandit > 0.8
   ```

2. **ShadowModeManager.swift** - Re-enable shadow mode:
   ```swift
   @Published var isActive: Bool = true      // was false
   @Published var interactionsRemaining: Int = 50  // was 0
   ```

3. **ContextualBandit.swift** - Re-enable shadow mode:
   ```swift
   private var shadowMode: Bool = true       // was false
   ```

## Project Structure

```
minnets/
├── MinnetsMac/                     # Swift/SwiftUI macOS app
│   ├── MinnetsMacApp.swift         # App entry, menubar setup
│   ├── FloatingPanelView.swift     # Main suggestion panel
│   ├── SuggestionCard.swift        # Individual suggestion UI
│   ├── OnboardingView.swift        # Permission onboarding flow
│   ├── ContextManager.swift        # Orchestrates capture & analysis
│   ├── BackendClient.swift         # HTTP client for backend
│   ├── Models.swift                # Data models
│   ├── ContextCapture/
│   │   ├── AppleScriptCapture.swift # Primary capture (browsers)
│   │   ├── AccessibilityCapture.swift # Fallback capture
│   │   ├── ScreenCapture.swift     # ScreenCaptureKit + OCR
│   │   ├── OCRCapture.swift        # OCR utilities
│   │   └── PermissionManager.swift # Permission handling
│   ├── Interruptibility/           # When to interrupt
│   │   ├── FlowStateGate.swift     # Layer 1: Hard blocks
│   │   ├── ConfusionDetector.swift # Layer 2: Need detection
│   │   ├── ContextualBandit.swift  # Layer 3: Personalization
│   │   └── InterruptibilityManager.swift
│   └── Feedback/                   # Learning from behavior
│       ├── ImplicitFeedbackTracker.swift
│       └── ShadowModeManager.swift
│
├── backend/                        # Python FastAPI
│   ├── main.py                     # API endpoints
│   ├── config.py                   # Settings from env (50+ configurable params)
│   ├── models.py                   # Pydantic models (VibeProfile, StrategyWeights, FeedbackRequest)
│   ├── retrieval/
│   │   ├── supermemory.py          # Supermemory API client
│   │   ├── exa_search.py           # Exa.ai web search
│   │   ├── cascade_router.py       # Weighted multi-strategy routing
│   │   ├── orthogonal_search.py    # 6 serendipity strategies
│   │   ├── vector_math.py          # True embedding arithmetic (PCA, antonym, bridge)
│   │   ├── judge_logger.py         # Training data collection (JSONL)
│   │   └── scoring.py              # MMR + temporal scoring
│   ├── synthesis/
│   │   ├── openai_client.py        # GPT for extraction, synthesis & vibe extraction
│   │   └── context_judge.py        # LLM-based cognitive state analyzer
│   └── tests/
│       ├── conftest.py             # Pytest configuration
│       └── test_api.py             # Comprehensive API tests
│
└── README.md
```

## API Endpoints

### `POST /analyze`

Analyze screen context and get suggestions.

```json
// Request
{
  "context": "Screen text content...",
  "app_name": "Visual Studio Code",
  "window_title": "main.py - minnets"
}

// Response
{
  "suggestions": [
    {
      "id": "uuid",
      "title": "LSTM Gradient Problems",
      "content": "Your notes from 2021 mention...",
      "reasoning": "Connects to transformer architecture...",
      "source": "supermemory",  // or "web_search", "orthogonal"
      "relevanceScore": 0.78,
      "noveltyScore": 0.85,
      "timestamp": "2024-01-15T10:30:00Z",
      "sourceUrl": null
    }
  ],
  "processingTimeMs": 1250,
  "retrievalPath": "weighted",  // or "orthogonal", "graph", "vector", "web", "vector_math"
  "confidence": "medium",  // "high", "medium", "low"
  "graphInsight": false,
  "shouldOfferWeb": false
}
```

### `POST /search-web`

Explicit web search trigger (when user clicks "Search Web" button).

```json
// Request
POST /search-web?query=positional play tactics

// Response
{
  "suggestions": [...],
  "retrievalPath": "web",
  "confidence": "low"
}
```

### `POST /save-to-memory`

Save a suggestion to Supermemory knowledge base.

```json
// Request
{
  "title": "Positional Play Tactics",
  "content": "Full content...",
  "sourceUrl": "https://example.com/article",
  "context": "Context when found..."
}
```

### `POST /test-exa`

Test endpoint to verify Exa search is working.

### `POST /test-tangential`

Test endpoint to see what tangential concepts are extracted from context.

### `POST /test-orthogonal`

Test endpoint to compare standard vs orthogonal retrieval. Shows side-by-side:
- Standard tangential search results
- Orthogonal search results (noise injection, archetype bridge, cross-domain)
- Extracted vibe profile

```json
// Response
{
  "vibe_profile": {
    "emotional_signatures": ["imperfect", "quiet", "handcrafted"],
    "archetype": "Someone who distrusts anything too polished...",
    "cross_domain_interests": ["Georgian restaurants with no website...", "ambient music with tape hiss..."],
    "anti_patterns": ["SEO-optimized", "Michelin-starred"],
    "source_domain": "ceramics"
  },
  "standard_search": {
    "query": "Japanese aesthetics pottery techniques",
    "results": [...]
  },
  "orthogonal_search": {
    "path": "orthogonal",
    "metadata": {"strategies_used": ["noise_injection", "archetype_bridge", "cross_domain"]},
    "results": [...]
  },
  "insight": "Standard search finds content ABOUT ceramics. Orthogonal search finds content that would delight someone who values: imperfect, quiet, handcrafted."
}
```

### `POST /test-vibe`

Test endpoint to see the full vibe profile extracted from content.

### `POST /test-context-judge`

Test endpoint to see how the Context Judge classifies different contexts.

```json
// Request (query params)
POST /test-context-judge?context=Some+content&app_name=Safari&window_title=Test

// Response
{
  "app_name": "Safari",
  "window_title": "Test",
  "context_preview": "Some content...",
  "weights": {
    "serendipity": 0.7,
    "relevance": 0.3,
    "source_web": 0.6,
    "source_local": 0.4,
    "reasoning": "User appears to be browsing casually..."
  },
  "interpretation": {
    "intent": "serendipity",
    "source": "web",
    "web_budget": "6 results",
    "local_budget": "4 results"
  }
}
```

### `POST /feedback`

Log user feedback on an insight for training data collection.

```json
// Request
{
  "requestId": "abc-123",
  "insightId": "insight-456",
  "feedbackType": "click",  // or "dwell", "dismiss", "thumbs_up", "thumbs_down", "save"
  "dwellTimeMs": 5000,      // optional
  "positionInList": 0,      // optional
  "metadata": {}            // optional
}

// Response
{
  "status": "logged",
  "request_id": "abc-123",
  "insight_id": "insight-456",
  "feedback_type": "click"
}
```

### `GET /health`

Health check endpoint.

## Configuration

Copy `env.template` to `.env` and fill in your API keys:

```env
# Required
OPENAI_API_KEY=sk-...          # https://platform.openai.com/api-keys
SUPERMEMORY_API_KEY=...        # https://supermemory.ai
EXA_API_KEY=...                # https://exa.ai

# Optional
HOST=127.0.0.1
PORT=8000
```

### OpenAI Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `OPENAI_MODEL` | `gpt-4.1` | Model for synthesis and extraction |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Model for embeddings |
| `CONTEXT_JUDGE_MODEL` | `gpt-4o-2024-08-06` | Model for context classification (structured output) |
| `JUDGE_LOG_PATH` | `training_data/router_decisions.jsonl` | Path for training data |

### Orthogonal Search Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `ORTHOGONAL_ENABLED` | `true` | Enable cross-domain serendipity in `/analyze` |
| `ORTHOGONAL_NOISE_SCALE` | `0.15` | Semantic noise level (0.1=close, 0.3=far) |
| `ORTHOGONAL_ARCHETYPE_ENABLED` | `true` | Enable archetype-based bridging |
| `ORTHOGONAL_VIBE_TEMPERATURE` | `0.8` | LLM temperature for vibe extraction |
| `ORTHOGONAL_TARGET_DOMAINS` | `["restaurants", "music", ...]` | Domains for cross-domain search |

### Vector Math Settings (PCA, Antonym, Bridge)

| Setting | Default | Description |
|---------|---------|-------------|
| `PCA_LAMBDA_SURPRISE` | `1.0` | Subtraction intensity (0=no effect, 1=full removal) |
| `PCA_MIN_MEMORIES` | `5` | Minimum memories for meaningful PCA |
| `PCA_NUM_COMPONENTS` | `2` | Number of dominant components to subtract |
| `ANTONYM_ALPHA` | `0.5` | Inversion strength (0=pure taste, 1=strong contrast) |
| `ANTONYM_TARGET_VIBES` | `["relaxation", "novelty", ...]` | Target vibes for steering |
| `BRIDGE_DOMAINS` | `["restaurant", "movie", ...]` | Domains for cross-modal bridge |

### Reranking Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `RERANK_POOL_SIZE` | `50` | Broad results to fetch before mathematical reranking |
| `RERANK_TOP_K` | `5` | Final number of results after reranking |

## Testing

Run the backend tests:

```bash
cd backend
source venv/bin/activate
pip install pytest pytest-asyncio
pytest tests/test_api.py -v
```

Tests cover:
- All API endpoints (`/health`, `/analyze`, `/search-web`, `/feedback`, `/test-*`, `/save-to-memory`)
- Pydantic models and validation (`StrategyWeights`, `VibeProfile`, `FeedbackType`)
- MMR doughnut scoring
- Orthogonal search strategies (all 6)
- Cascade router paths (including vector math paths)
- Context Judge fallback behavior
- Judge Logger training data collection

## License

Heath School

