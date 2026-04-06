# Project Jarvis

Real-time AI assistant — voice pipeline, persistent memory, agentic tools, vision, holographic HUD.

## Architecture

```
Mic → Wake Word (Porcupine) → STT (Deepgram) → Intent Router (Haiku)
    → Memory Retrieval (Chroma + Neo4j + SQLite)
    → LLM (Sonnet / Haiku / Qwen local)
    → Tool Executor (web, OS, APIs, calendar, code)
    → TTS (ElevenLabs / Kokoro)
    → HUD (React + Three.js)
```

## Setup

### 1. Clone & configure

```bash
cp .env.example .env
# Fill in all API keys in .env
```

### 2. Start infrastructure

```bash
docker-compose up -d
```

### 3. Install Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 4. Start the backend

```bash
uvicorn backend.main:app --reload --port 8000
```

### 5. Start the voice client (local machine)

```bash
python voice_client.py
```

### 6. Start the HUD

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

## Local / Offline Mode

Set `LOCAL_MODE=true` in `.env` and run Ollama:

```bash
ollama pull qwen2.5:7b
ollama serve
```

## Project Structure

```
jarvis/
├── backend/
│   ├── main.py              # FastAPI + WebSocket server
│   ├── config.py            # Settings from .env
│   ├── voice/
│   │   ├── wake_word.py     # Porcupine wake word
│   │   ├── stt.py           # Deepgram streaming STT
│   │   └── tts.py           # ElevenLabs streaming TTS
│   ├── brain/
│   │   ├── llm.py           # Claude + Ollama clients
│   │   ├── router.py        # Intent classifier
│   │   └── orchestrator.py  # Agentic loop
│   ├── memory/
│   │   ├── vector.py        # Chroma vector memory
│   │   ├── graph.py         # Neo4j graph memory
│   │   ├── session.py       # Redis session cache
│   │   ├── store.py         # SQLite persistent store
│   │   └── assembler.py     # Memory context builder
│   ├── tools/
│   │   └── registry.py      # All tool definitions + executors
│   └── vision/
│       └── screen.py        # Screenshot + camera capture
├── agents/
│   └── proactive.py         # Background alert scheduler
├── frontend/
│   └── src/
│       ├── App.tsx           # Main HUD
│       └── components/
│           ├── ArcReactor.tsx  # Three.js visualizer
│           └── Waveform.tsx    # Audio waveform
├── voice_client.py          # Local voice loop
├── docker-compose.yml       # Redis, Neo4j, Chroma
└── requirements.txt
```

## Phases

| Phase | Weeks | Focus |
|-------|-------|-------|
| 1 | 1–2 | Voice core: wake word → STT → LLM → TTS |
| 2 | 3–5 | Memory: vector + graph + SQLite |
| 3 | 6–9 | Tools: web, OS, APIs, calendar, code |
| 4 | 10–13 | Vision: screen capture, camera, proactive alerts |
| 5 | 14–16 | HUD polish, latency optimization, local LLM |

## Latency Budget

| Component | Target |
|-----------|--------|
| Wake word | ~10ms |
| STT (TTFT) | ~150ms |
| Memory retrieval | ~50ms |
| LLM first token | 150–400ms |
| TTS first audio | ~75ms |
| **Total perceived** | **~400–600ms** |
