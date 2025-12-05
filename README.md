# Minnets

**Proactive Knowledge Companion for macOS**

Minnets watches what you're doing and surfaces relevant insights from your personal knowledge base (Supermemory) and the web (Exa.ai). Unlike chat interfaces, Minnets proactively suggests information - you don't need to know what to ask.

## Key Features

- **Proactive Suggestions**: No prompting required - insights appear when relevant
- **Graph Pivot Retrieval**: Finds *connected but different* content, not just similar text
- **Smart Interruptibility**: 3-layer system prevents annoying you during flow states
- **Implicit Learning**: Learns your preferences from hover, expand, copy, dismiss signals
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
        │                       ▼
        │               ┌──────────────────┐
        │               │  OpenAI + Exa    │
        │               └──────────────────┘
        ▼
┌─────────────────┐     ┌──────────────────┐
│  Floating Panel │────▶│ Implicit Feedback│
│  (Suggestions)  │     │ Tracker          │
└─────────────────┘     └──────────────────┘
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

Traditional RAG shows you what's most similar to your context - but that's often redundant. Minnets uses a cascade architecture with tangential concept extraction:

### Concept Extraction
- Extracts **tangential concepts** (related but different topics)
- Avoids searching for the main subject (user already has that)
- Example: Reading about "Pep Guardiola" → search for "positional play tactics", not "Pep Guardiola"

### Cascade Router (Graph → Vector → Web)

1. **Graph Pivot Check**: Find graph-connected insights
   - Find anchors via vector search
   - Filter echo chamber (>85% similarity → pivot to neighbors)
   - Keep sweet spot anchors (65-85% similarity)
   - Traverse graph relationships (derives, extends, contrast)

2. **Vector Check**: Direct similarity search
   - High confidence (>85%) → Show KB results
   - Medium (65-85%) → Show KB + offer web search
   - Low (<65%) → Trigger web search

3. **Web Search**: When local knowledge is insufficient
   - Search for tangential concepts
   - Filter out results about main subject (redundancy avoidance)

### Scoring
- **MMR Doughnut**: Sweet spot is 65-85% similarity - related but novel
- **Temporal Boost**: Older, unaccessed memories get priority

## Setup

### Prerequisites

- macOS 14.0+
- Python 3.11+
- Xcode 15+
- API keys for:
  - [OpenAI](https://platform.openai.com/api-keys) (GPT-5.1)
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

The retrieval pipeline uses a **cascade architecture** with tangential concept extraction:

```python
# 1. Extract TANGENTIAL concepts (not the main subject)
# If user is reading about "Pep Guardiola", extract:
# ["positional play tactics", "tiki-taka philosophy", "Johan Cruyff influence"]
# NOT ["Pep Guardiola", "Manchester City"]
concepts = extract_tangential_concepts(screen_text)
main_subject = extract_main_subject(screen_text)  # For redundancy filtering

# 2. Cascade Router: Graph → Vector → Web
search_query = " ".join(concepts[:3])

# Step 1: Graph Pivot Check (Serendipity)
graph_result = cascade_router.check_graph(query)
if graph_result:
    # Found graph-connected insights - highest value
    return graph_result

# Step 2: Vector Check (Direct similarity)
vector_result, confidence = cascade_router.check_vector(query)
if confidence == HIGH:
    return vector_result  # Definitely in your notes
elif confidence == MEDIUM:
    return vector_result  # Might be in notes, offer web search

# Step 3: Web Search Fallback
web_results = exa.search_for_connections(
    concepts=concepts,
    exclude_text=main_subject  # Filter redundant results
)

# 4. Score with MMR doughnut model
scored = apply_mmr_scoring(all_results)
# - Echo chamber (>0.85): Penalize 50%
# - Sweet spot (0.65-0.85): Bonus 20%
# - Too distant (<0.65): Lower score

# 5. Temporal boost for forgotten memories
scored = apply_temporal_boost(scored)  # log(days_since_accessed)

# 6. Synthesize human-readable suggestions
suggestions = synthesize(scored, context, emphasize_novelty=True)
```

**Key Insight**: Minnets searches for *related but different* concepts, not the main subject. This avoids redundancy and surfaces serendipitous connections.

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

### Shadow Mode (Cold Start)

For the first 50 interactions, Minnets runs in "Shadow Mode":
- Generates suggestions but **doesn't show them**
- If you manually search for something it would have suggested → massive positive signal
- Calibrates the model without any annoyance

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
│   ├── config.py                   # Settings from env
│   ├── models.py                   # Pydantic models
│   ├── retrieval/
│   │   ├── supermemory.py          # Supermemory API client
│   │   ├── exa_search.py           # Exa.ai web search
│   │   ├── cascade_router.py       # Cascade: Graph → Vector → Web
│   │   └── scoring.py              # MMR + temporal scoring
│   └── synthesis/
│       └── openai_client.py        # GPT for extraction & synthesis
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
      "source": "supermemory",
      "relevanceScore": 0.78,
      "noveltyScore": 0.85,
      "timestamp": "2024-01-15T10:30:00Z",
      "sourceUrl": null
    }
  ],
  "processingTimeMs": 1250,
  "retrievalPath": "graph",
  "confidence": "high",
  "graphInsight": true,
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

## License

MIT

