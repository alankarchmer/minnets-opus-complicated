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

## The "Graph Pivot" Strategy

Traditional RAG shows you what's most similar to your context - but that's often redundant. Minnets uses a different approach:

1. **Find the Anchor**: Vector search finds memories similar to your screen content
2. **Filter Echo Chamber**: Discard results with >85% similarity (too redundant)
3. **Pivot to Neighbors**: Traverse the knowledge graph to find *connected but different* content
4. **Score with MMR Doughnut**: Sweet spot is 65-85% similarity - related but novel
5. **Boost Forgotten Memories**: Older, unaccessed memories get priority

## Setup

### Prerequisites

- macOS 14.0+
- Python 3.11+
- Xcode 15+
- API keys for:
  - [OpenAI](https://platform.openai.com/api-keys) (GPT-4)
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

**Important**: Grant Accessibility permissions when prompted. This allows Minnets to read text from your screen.

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

Minnets captures text from your frontmost window using:
1. **Accessibility API** (preferred) - Direct text extraction
2. **OCR fallback** - Screen capture + Vision framework

Captures happen every 15 seconds when context changes significantly.

### Retrieval Pipeline

```python
# 1. Extract concepts from screen
concepts = extract_concepts(screen_text)  # ["transformers", "attention", "PyTorch"]

# 2. Find anchors in Supermemory
anchors = supermemory.search(concepts)  # High similarity matches

# 3. Filter echo chamber
anchors = [a for a in anchors if a.similarity < 0.85]

# 4. Graph pivot - find neighbors
neighbors = []
for anchor in high_similarity_anchors:
    related = supermemory.get_related(anchor, ["derives", "extends"])
    neighbors.extend(related)

# 5. Score with MMR doughnut
scored = apply_mmr_scoring(neighbors)  # Sweet spot: 0.65-0.85

# 6. Temporal boost for forgotten memories
scored = apply_temporal_boost(scored)  # log(days_since_accessed)

# 7. Synthesize human-readable suggestions
suggestions = synthesize(scored, context)
```

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
│   ├── ContextManager.swift        # Orchestrates capture & analysis
│   ├── BackendClient.swift         # HTTP client for backend
│   ├── Models.swift                # Data models
│   ├── ContextCapture/
│   │   ├── AccessibilityCapture.swift
│   │   └── OCRCapture.swift
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
│   │   ├── graph_pivot.py          # Graph Pivot strategy
│   │   ├── cascade_router.py       # Graph → Vector → Web
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
      "relevance_score": 0.78,
      "novelty_score": 0.85,
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ],
  "processing_time_ms": 1250
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

## License

MIT

