# Jarvis Full-Stack AI Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready omnipotent AI assistant with 47 capabilities, 8 agent modules, 6-layer memory, voice pipeline with <450ms latency, and security-first architecture.

**Architecture:** Modular agent-based system with FastAPI WebSocket backend, React/Three.js HUD, Redis pub/sub, Chroma vector DB, Neo4j graph DB, SQLite persistent store, and multi-provider LLM support (Anthropic/Gemini/Ollama). Tools are registered centrally and dispatched by an orchestrator using agentic loops. Memory layers are assembled dynamically per-query using parallel retrieval. Voice pipeline uses Porcupine wake word → Silero VAD → Deepgram streaming STT → LLM → ElevenLabs Flash TTS.

**Tech Stack:**
- **Backend:** Python 3.11+, FastAPI, WebSocket, async/await
- **Voice:** Porcupine, Deepgram, ElevenLabs, Silero VAD
- **LLM:** Anthropic Claude, Google Gemini, Ollama (local)
- **Memory:** Redis, ChromaDB, Neo4j, SQLite/SQLCipher
- **Frontend:** React 18, TypeScript, Three.js, Vite
- **Tools:** Playwright, PyAutoGUI, APScheduler, Home Assistant API, OAuth2
- **Infrastructure:** Docker Compose, Nginx, Let's Encrypt

---

## Current State Assessment

### ✅ Implemented (Skeleton/Basics)
- FastAPI WebSocket server with voice and HUD endpoints
- Basic voice pipeline components (wake word, STT, TTS - not fully integrated)
- Memory architecture skeleton (session, vector, graph, store, assembler)
- Intent router and orchestrator with agentic loop
- 8 basic tools: web_search, weather, run_code, os_open_app, screenshot, stock_price, smart_home_control, add_reminder
- Proactive agent skeleton (reminders, weather alerts, system health)
- React HUD with Three.js Arc Reactor visualization
- Docker Compose (Redis, Neo4j, Chroma)
- Multi-provider LLM client (Anthropic/Gemini/Ollama)
- Configuration management

### ❌ Missing (Critical Gaps)
1. **39 of 47 capabilities** - Only 8 tools implemented
2. **7 of 8 agent modules** - Only proactive skeleton exists
3. **Full voice integration** - STT/TTS not wired into main.py WebSocket flow
4. **Security framework** - No encryption, auth, or access control
5. **Testing infrastructure** - Zero tests
6. **Advanced memory** - Procedural memory, world model not implemented
7. **Vision tools** - Only screen capture, no OCR, analysis pipelines
8. **Developer tools** - No git integration, database tools, API testing
9. **Communication tools** - No email, calendar, WhatsApp, Slack
10. **Browser automation** - Basic web_search only, no form filling, scraping framework
11. **File management** - No file CRUD, search, organization tools
12. **Finance tracking** - No expense logging, budget management
13. **Health tracking** - No habit coaching, health metrics
14. **Travel tools** - No flight search, booking integration
15. **Performance optimization** - No caching strategy, latency monitoring
16. **Observability** - No logging, metrics, tracing
17. **Error handling** - Basic try/catch only, no resilience patterns
18. **Documentation** - No API docs, architecture docs, user guide

---

## Architecture Decision Records

### ADR-001: Modular Monolith Architecture

**Status:** Proposed

**Context:**
Need to organize 47 capabilities and 8 agents while maintaining development velocity. Team is small (1-3 developers). Domain boundaries are clear (communication, developer tools, smart home, etc.).

**Decision:**
Use **modular monolith** architecture. Each agent is a Python module under `backend/agents/` with clear boundaries. Tools are registered centrally in `backend/tools/registry.py`. No microservices - avoid distributed complexity until proven necessary.

**Consequences:**
- ✅ Easier debugging (single process)
- ✅ Faster development (no inter-service communication)
- ✅ Simple deployment (single Docker container)
- ✅ Can extract agents to microservices later if needed
- ❌ No independent scaling per agent
- ❌ Single point of failure (mitigated with clustering later)

---

### ADR-002: Multi-Provider LLM Strategy

**Status:** Accepted

**Context:**
Users may prefer different LLM providers (Anthropic for quality, Gemini for speed, Ollama for privacy). Cost and latency vary by use case.

**Decision:**
Support **Anthropic, Google Gemini, and Ollama** with automatic routing:
- **Fast tasks (routing, simple queries):** Gemini Flash or Claude Haiku
- **Complex tasks (reasoning, code generation):** Claude Sonnet or Gemini Pro
- **Privacy-sensitive tasks:** Ollama (local)
- **Tool use:** Claude Sonnet or Gemini Pro (best function calling)

**Consequences:**
- ✅ Flexibility for users
- ✅ Cost optimization (use cheaper models when appropriate)
- ✅ Local-first option for privacy
- ❌ Increased complexity in LLM client
- ❌ Provider-specific quirks to handle (streaming differences, token limits)

---

### ADR-003: Security-First Design

**Status:** Proposed

**Context:**
Jarvis has extensive system access (terminal, files, browser, smart home). This is a high-value attack target.

**Decision:**
Implement **defense in depth**:
1. **Encryption at rest:** SQLCipher for SQLite, encrypted volumes for Chroma/Neo4j
2. **Encryption in transit:** TLS for all connections (WebSocket, Redis, Neo4j)
3. **Authentication:** JWT tokens for WebSocket connections, API key rotation
4. **Authorization:** Tool-level permissions (user must approve sensitive actions)
5. **Sandboxing:** Code execution in Docker containers, not host
6. **Audit logging:** All tool executions logged with user, timestamp, result
7. **Secrets management:** Environment variables + Vault integration for production

**Consequences:**
- ✅ Defense against data breaches
- ✅ Compliance with privacy regulations
- ✅ User trust
- ❌ Increased complexity and setup time
- ❌ Performance overhead for encryption

---

### ADR-004: Voice Pipeline Latency Target (<450ms)

**Status:** Accepted

**Context:**
Conversational AI feels natural only if response latency is under 450ms perceived by user.

**Decision:**
Optimize each stage:
1. **Wake word (Porcupine):** ~10ms
2. **VAD (Silero):** ~20ms (parallel with wake word detection)
3. **STT (Deepgram streaming):** ~150ms TTFT (time to first token)
4. **Context fetch:** ~50ms (parallel: vector search, graph lookup, session cache)
5. **LLM streaming:** ~200-400ms TTFT (Claude/Gemini)
6. **TTS (ElevenLabs Flash):** ~75ms

**Total target:** 450-550ms end-to-end

**Optimizations:**
- Start context fetch in parallel while STT is still processing
- Stream LLM response sentence-by-sentence to TTS
- Use Redis caching for repeated queries
- Preload common responses

**Consequences:**
- ✅ Natural conversation feel
- ✅ Competitive with human response times
- ❌ Requires careful profiling and optimization
- ❌ May need fallback to text-only mode under load

---

### ADR-005: Event-Driven Proactive Intelligence

**Status:** Proposed

**Context:**
Jarvis should anticipate user needs without explicit requests (proactive alerts, suggestions, background workflows).

**Decision:**
Use **APScheduler for scheduled checks** and **Redis pub/sub for real-time events**:
- Scheduler runs checks every 30s-60m (reminders, weather, system health, stock alerts)
- Events published to Redis channels (e.g., `alerts:{session_id}`)
- WebSocket subscribers receive proactive alerts
- Background agents can execute multi-step workflows and publish progress updates

**Consequences:**
- ✅ Non-blocking proactive features
- ✅ Real-time alerts
- ❌ Scheduler complexity (APScheduler can drift)
- ❌ Need to handle missed alerts after downtime

---

## File Structure

### Backend (`/backend`)

```
backend/
├── main.py                          # FastAPI app, WebSocket endpoints, lifecycle
├── config.py                        # Pydantic Settings, environment config
│
├── voice/                           # Voice pipeline
│   ├── wake_word.py                 # Porcupine wake word detector
│   ├── vad.py                       # Silero VAD (CREATE)
│   ├── stt.py                       # Deepgram streaming STT
│   ├── tts.py                       # ElevenLabs streaming TTS
│   └── pipeline.py                  # End-to-end voice orchestrator (CREATE)
│
├── brain/                           # Core intelligence
│   ├── llm.py                       # Multi-provider LLM client
│   ├── router.py                    # Intent classification
│   ├── orchestrator.py              # Main orchestration logic
│   └── prompts.py                   # System prompts, templates (CREATE)
│
├── memory/                          # 6-layer memory architecture
│   ├── session.py                   # Redis working memory
│   ├── vector.py                    # Chroma episodic memory
│   ├── store.py                     # SQLite semantic memory
│   ├── graph.py                     # Neo4j social graph
│   ├── assembler.py                 # Context assembly
│   ├── procedural.py                # Learned patterns (CREATE)
│   └── world_model.py               # User preferences, habits (CREATE)
│
├── vision/                          # Vision/perception tools
│   ├── screen.py                    # Screen capture
│   ├── ocr.py                       # OCR extraction (CREATE)
│   ├── camera.py                    # Camera capture (CREATE)
│   └── analysis.py                  # Image understanding (CREATE)
│
├── agents/                          # 8 specialized agents
│   ├── web_research.py              # Web & Research Agent (CREATE)
│   ├── communication.py             # Communication Agent (CREATE)
│   ├── computer_control.py          # Computer Control Agent (CREATE)
│   ├── developer.py                 # Developer Agent (CREATE)
│   ├── smart_environment.py         # Smart Environment Agent (CREATE)
│   ├── life_management.py           # Life Management Agent (CREATE)
│   ├── knowledge.py                 # Knowledge Agent (CREATE)
│   └── planner.py                   # Multi-step Planner Agent (CREATE)
│
├── tools/                           # Tool implementations
│   ├── registry.py                  # Tool executor, definitions
│   ├── web.py                       # Web search, scraping (CREATE)
│   ├── browser.py                   # Browser automation (CREATE)
│   ├── email.py                     # Email CRUD (CREATE)
│   ├── calendar.py                  # Calendar CRUD (CREATE)
│   ├── files.py                     # File management (CREATE)
│   ├── terminal.py                  # Terminal control (CREATE)
│   ├── code.py                      # Code execution (CREATE)
│   ├── git.py                       # Git operations (CREATE)
│   ├── database.py                  # Database queries (CREATE)
│   ├── smart_home.py                # Home Assistant, Spotify (CREATE)
│   ├── finance.py                   # Finance tracking (CREATE)
│   ├── travel.py                    # Travel search (CREATE)
│   ├── health.py                    # Health tracking (CREATE)
│   ├── notes.py                     # Notes & journaling (CREATE)
│   ├── tasks.py                     # Task management (CREATE)
│   ├── contacts.py                  # Contact lookup (CREATE)
│   ├── translation.py               # Translation (CREATE)
│   ├── crypto.py                    # Crypto prices (CREATE)
│   └── utils.py                     # Shared tool utilities (CREATE)
│
├── security/                        # Security framework (CREATE)
│   ├── encryption.py                # SQLCipher, Fernet encryption
│   ├── auth.py                      # JWT authentication
│   ├── permissions.py               # Tool-level permissions
│   ├── audit.py                     # Audit logging
│   └── sandbox.py                   # Code execution sandbox
│
├── observability/                   # Monitoring (CREATE)
│   ├── logging_config.py            # Structured logging
│   ├── metrics.py                   # Prometheus metrics
│   └── tracing.py                   # OpenTelemetry tracing
│
└── tests/                           # Test suite (CREATE)
    ├── test_voice/
    ├── test_memory/
    ├── test_tools/
    ├── test_agents/
    └── test_integration/
```

---

## Implementation Phases Overview

### Phase 1: Voice Core - Talking Skeleton (Weeks 1-3)
**Goal:** End-to-end voice conversation with <600ms latency
- Integrate Silero VAD
- Create voice pipeline orchestrator
- Add latency monitoring
- Optimize for target latency

### Phase 2: Memory Awakens (Weeks 4-6)
**Goal:** Full 6-layer memory system
- Implement procedural memory
- Build world model
- Enhance context assembly
- Add memory consolidation

### Phase 3: First Tools - Jarvis Acts (Weeks 7-10)
**Goal:** 20 core tools operational
- File management tools
- Browser automation tools
- Communication tools (email, calendar)
- Developer tools (git, terminal)

### Phase 4: Developer Powers (Weeks 11-13)
**Goal:** Full developer assistance
- Code execution sandbox
- Database tools
- API testing tools
- Code review assistant

### Phase 5: Vision & Perception (Weeks 14-17)
**Goal:** Vision capabilities
- OCR integration
- Screen analysis
- Camera analysis
- Document understanding

### Phase 6: Proactive Intelligence (Weeks 18-21)
**Goal:** Anticipatory assistant
- Pattern recognition
- Predictive suggestions
- Background workflows
- Multi-step planner

### Phase 7: HUD & Finishing (Weeks 22-26)
**Goal:** Production-ready system
- Enhanced HUD
- Security hardening
- Testing & documentation
- Deployment automation

---

## Detailed Phase 1 Tasks: Voice Core

### Task 1.1: Integrate Silero VAD

**Files:**
- Create: `backend/voice/vad.py`
- Create: `backend/tests/test_voice/test_vad.py`

- [ ] **Step 1: Write the failing test for VAD**

```python
# backend/tests/test_voice/test_vad.py
import asyncio
import pytest
from backend.voice.vad import VoiceActivityDetector

@pytest.mark.asyncio
async def test_vad_detects_speech():
    """Test that VAD correctly identifies speech chunks."""
    vad = VoiceActivityDetector()
    
    # Load test audio file with known speech
    with open("tests/fixtures/speech_sample.wav", "rb") as f:
        audio_data = f.read()
    
    chunks_processed = 0
    speech_detected = False
    
    async for is_speech in vad.process_stream(audio_data):
        chunks_processed += 1
        if is_speech:
            speech_detected = True
    
    assert chunks_processed > 0, "No chunks processed"
    assert speech_detected, "VAD failed to detect speech"

@pytest.mark.asyncio
async def test_vad_silence_ignored():
    """Test that VAD ignores silence."""
    vad = VoiceActivityDetector()
    silence = b'\x00' * 32000  # 1 second of silence
    
    speech_detected = False
    async for is_speech in vad.process_stream(silence):
        if is_speech:
            speech_detected = True
    
    assert not speech_detected, "VAD falsely detected speech in silence"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_voice/test_vad.py -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Write VAD implementation**

```python
# backend/voice/vad.py
import asyncio
import torch
import numpy as np

class VoiceActivityDetector:
    """Silero VAD for speech detection."""
    
    def __init__(self, threshold: float = 0.5, sample_rate: int = 16000):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.model = None
        self._loaded = False
    
    async def load_model(self):
        """Load Silero VAD model asynchronously."""
        if self._loaded:
            return
        
        def _load():
            model, _ = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
            )
            return model
        
        self.model = await asyncio.to_thread(_load)
        self._loaded = True
    
    async def process_stream(self, audio_data: bytes, chunk_size: int = 512):
        """Process audio stream and yield speech detection results."""
        await self.load_model()
        
        audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        audio_tensor = torch.from_numpy(audio_array)
        
        for i in range(0, len(audio_tensor), chunk_size):
            chunk = audio_tensor[i:i + chunk_size]
            if len(chunk) < chunk_size:
                chunk = torch.nn.functional.pad(chunk, (0, chunk_size - len(chunk)))
            
            with torch.no_grad():
                speech_prob = self.model(chunk, self.sample_rate).item()
            
            yield speech_prob > self.threshold
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_voice/test_vad.py -v`
Expected: PASS (after creating test fixtures)

- [ ] **Step 5: Create test audio fixtures**

```bash
mkdir -p tests/fixtures
# Download sample audio or generate with ffmpeg
```

- [ ] **Step 6: Commit**

```bash
git add backend/voice/vad.py backend/tests/test_voice/test_vad.py
git commit -m "feat(voice): add Silero VAD for speech detection"
```

---

### Task 1.2: Create Voice Pipeline Orchestrator

**Files:**
- Create: `backend/voice/pipeline.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_voice/test_pipeline.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_voice/test_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch
from backend.voice.pipeline import VoicePipeline

@pytest.mark.asyncio
async def test_voice_pipeline_flow():
    """Test complete voice pipeline flow."""
    mock_on_response = AsyncMock()
    pipeline = VoicePipeline(
        session_id="test-session",
        on_response=mock_on_response
    )
    
    # Simulate wake word
    await pipeline.on_wake_word()
    assert pipeline.is_listening
    
    # Simulate transcript
    await pipeline.on_final_transcript("What's the weather?")
    assert not pipeline.is_listening
```

- [ ] **Step 2: Implement voice pipeline**

```python
# backend/voice/pipeline.py
import asyncio
import json
import websockets
from backend.voice.wake_word import WakeWordDetector
from backend.voice.vad import VoiceActivityDetector
from backend.voice.stt import StreamingSTT
from backend.voice.tts import StreamingTTS

class VoicePipeline:
    """End-to-end voice pipeline orchestrator."""
    
    def __init__(
        self,
        session_id: str,
        on_response: callable,
        backend_url: str = "ws://localhost:8000/ws/voice",
        timeout_seconds: int = 30,
    ):
        self.session_id = session_id
        self.on_response = on_response
        self.backend_url = f"{backend_url}/{session_id}"
        self.timeout_seconds = timeout_seconds
        
        self.wake_word = WakeWordDetector(on_detected=self.on_wake_word)
        self.vad = VoiceActivityDetector()
        self.stt = None
        self.tts = StreamingTTS()
        self.ws = None
        
        self.is_listening = False
        self.last_activity = None
        self._running = False
    
    def start(self):
        """Start the voice pipeline."""
        self._running = True
        self.wake_word.start()
        asyncio.create_task(self._connect_backend())
        asyncio.create_task(self._monitor_timeout())
    
    def stop(self):
        """Stop the voice pipeline."""
        self._running = False
        self.wake_word.stop()
        if self.stt:
            asyncio.create_task(self.stt.stop())
    
    async def on_wake_word(self):
        """Handle wake word detection."""
        if self.is_listening:
            return
        
        print("[Jarvis] Listening...")
        self.is_listening = True
        self.last_activity = asyncio.get_event_loop().time()
        
        self.stt = StreamingSTT(
            on_transcript=self.on_partial_transcript,
            on_final=self.on_final_transcript,
        )
        await self.stt.start()
    
    async def on_partial_transcript(self, text: str):
        """Handle partial transcript."""
        print(f"\r[...] {text}", end="", flush=True)
        self.last_activity = asyncio.get_event_loop().time()
    
    async def on_final_transcript(self, text: str):
        """Handle final transcript."""
        if not text.strip():
            self.is_listening = False
            return
        
        print(f"\n[You] {text}")
        
        if self.ws:
            await self.ws.send(json.dumps({"type": "transcript", "text": text}))
        
        self.is_listening = False
        if self.stt:
            await self.stt.stop()
    
    async def _connect_backend(self):
        """Connect to backend WebSocket."""
        async with websockets.connect(self.backend_url) as ws:
            self.ws = ws
            async for raw in ws:
                msg = json.loads(raw)
                await self._handle_backend_message(msg)
    
    async def _handle_backend_message(self, msg: dict):
        """Handle messages from backend."""
        if msg["type"] == "done":
            response = msg["text"]
            print(f"[Jarvis] {response}")
            await self.on_response(response)
            await self.tts.speak(response)
        elif msg["type"] == "thinking":
            print("[Jarvis] Thinking...", end="", flush=True)
    
    async def _monitor_timeout(self):
        """Monitor for inactivity timeout."""
        while self._running:
            if self.is_listening and self.last_activity:
                elapsed = asyncio.get_event_loop().time() - self.last_activity
                if elapsed > self.timeout_seconds:
                    print("\n[Jarvis] Timeout. Say 'Hey Jarvis' to activate.")
                    self.is_listening = False
                    if self.stt:
                        await self.stt.stop()
            
            await asyncio.sleep(1)
```

- [ ] **Step 3: Run tests and commit**

Run: `pytest backend/tests/test_voice/test_pipeline.py -v`
Expected: PASS

```bash
git add backend/voice/pipeline.py backend/tests/test_voice/test_pipeline.py
git commit -m "feat(voice): integrate end-to-end voice pipeline orchestrator"
```

---

### Task 1.3: Add Latency Monitoring

**Files:**
- Create: `backend/voice/latency_tracker.py`
- Create: `backend/tests/test_voice/test_latency.py`

- [ ] **Step 1: Write latency tracker**

```python
# backend/voice/latency_tracker.py
import time
from typing import Dict
from backend.config import get_settings

settings = get_settings()

class LatencyTracker:
    """Track latency across voice pipeline stages."""
    
    def __init__(self, target_ms: int = None):
        self.target_ms = target_ms or 555  # Sum of all target latencies
        self.records: Dict[str, float] = {}
        self.start_time = time.time()
    
    def record(self, stage: str, latency_ms: float):
        """Record latency for a pipeline stage."""
        self.records[stage] = latency_ms
    
    def get_summary(self) -> dict:
        """Get latency summary."""
        total = sum(self.records.values())
        return {
            **self.records,
            "total": total,
            "within_target": total <= self.target_ms,
            "target": self.target_ms,
        }
    
    def reset(self):
        """Reset tracker for new interaction."""
        self.records.clear()
        self.start_time = time.time()
```

- [ ] **Step 2: Integrate into pipeline and commit**

```bash
git add backend/voice/latency_tracker.py
git commit -m "feat(voice): add latency tracking for optimization"
```

---

## Detailed Phase 2 Tasks: Memory Awakens

### Task 2.1: Implement Procedural Memory

**Files:**
- Create: `backend/memory/procedural.py`
- Create: `backend/tests/test_memory/test_procedural.py`

- [ ] **Step 1: Write procedural memory**

```python
# backend/memory/procedural.py
import json
import datetime
from collections import defaultdict
from typing import Dict, List, Optional
from backend.memory.store import PersistentStore

class ProceduralMemory:
    """Learn and recall user patterns/habits."""
    
    def __init__(self, store: PersistentStore = None):
        self.store = store
        self.patterns: Dict[str, dict] = defaultdict(lambda: {
            "frequency": 0,
            "params": {},
            "timestamps": [],
        })
    
    async def record_action(
        self,
        action: str,
        params: dict,
        timestamp: datetime.datetime = None
    ):
        """Record a user action pattern."""
        timestamp = timestamp or datetime.datetime.utcnow()
        
        pattern = self.patterns[action]
        pattern["frequency"] += 1
        pattern["timestamps"].append(timestamp.isoformat())
        
        # Track most common params
        param_key = json.dumps(params, sort_keys=True)
        if "param_counts" not in pattern:
            pattern["param_counts"] = defaultdict(int)
        pattern["param_counts"][param_key] += 1
        
        # Update most common params
        max_count = max(pattern["param_counts"].values())
        for pk, count in pattern["param_counts"].items():
            if count == max_count:
                pattern["params"] = json.loads(pk)
                break
        
        # Persist to store if available
        if self.store:
            await self.store.log_task(action, json.dumps(params), "procedural_memory")
    
    async def get_pattern(self, action: str) -> Optional[dict]:
        """Get learned pattern for an action."""
        pattern = self.patterns.get(action)
        if not pattern or pattern["frequency"] < 3:
            return None
        
        return {
            "action": action,
            "frequency": pattern["frequency"],
            "params": pattern["params"],
            "last_occurred": pattern["timestamps"][-1] if pattern["timestamps"] else None,
        }
    
    async def suggest_actions(self, context: dict = None) -> List[dict]:
        """Suggest actions based on patterns and context."""
        suggestions = []
        
        for action, pattern in self.patterns.items():
            if pattern["frequency"] >= 3:
                # Simple time-based suggestion (can be enhanced)
                suggestions.append({
                    "action": action,
                    "confidence": min(pattern["frequency"] / 10.0, 1.0),
                    "params": pattern["params"],
                })
        
        return sorted(suggestions, key=lambda x: x["confidence"], reverse=True)[:5]
```

- [ ] **Step 2: Write tests and commit**

```python
# backend/tests/test_memory/test_procedural.py
import pytest
from backend.memory.procedural import ProceduralMemory

@pytest.mark.asyncio
async def test_procedural_memory_learns_patterns():
    proc_mem = ProceduralMemory()
    
    await proc_mem.record_action("check_weather", {"location": "Paris"})
    await proc_mem.record_action("check_weather", {"location": "Paris"})
    await proc_mem.record_action("check_weather", {"location": "Paris"})
    
    pattern = await proc_mem.get_pattern("check_weather")
    assert pattern is not None
    assert pattern["frequency"] == 3
    assert pattern["params"]["location"] == "Paris"
```

```bash
git add backend/memory/procedural.py backend/tests/test_memory/test_procedural.py
git commit -m "feat(memory): implement procedural memory for pattern learning"
```

---

### Task 2.2: Implement World Model

**Files:**
- Create: `backend/memory/world_model.py`
- Create: `backend/tests/test_memory/test_world_model.py`

- [ ] **Step 1: Write world model**

```python
# backend/memory/world_model.py
from typing import Dict, Any, Optional
from backend.memory.store import PersistentStore

class WorldModel:
    """User preferences, habits, and context."""
    
    def __init__(self, store: PersistentStore):
        self.store = store
    
    async def get_preference(self, key: str) -> Optional[str]:
        """Get user preference."""
        return await self.store.get_preference(key)
    
    async def set_preference(self, key: str, value: str):
        """Set user preference."""
        await self.store.set_preference(key, value)
    
    async def get_user_context(self) -> Dict[str, Any]:
        """Get full user context for LLM prompting."""
        prefs = await self.store.get_all_preferences()
        
        context_parts = []
        if prefs.get("location"):
            context_parts.append(f"User location: {prefs['location']}")
        if prefs.get("timezone"):
            context_parts.append(f"User timezone: {prefs['timezone']}")
        if prefs.get("name"):
            context_parts.append(f"User name: {prefs['name']}")
        
        return {
            "preferences": prefs,
            "context_text": "\n".join(context_parts) if context_parts else "",
        }
    
    async def infer_preference(self, action: str, params: dict):
        """Infer and store preferences from user actions."""
        # Simple preference inference
        if action == "check_weather" and "location" in params:
            current = await self.get_preference("location")
            if not current:
                await self.set_preference("location", params["location"])
```

- [ ] **Step 2: Write tests and commit**

```bash
git add backend/memory/world_model.py backend/tests/test_memory/test_world_model.py
git commit -m "feat(memory): implement world model for user preferences"
```

---

## Remaining Phases (High-Level Roadmap)

### Phase 3: First Tools (Weeks 7-10)

**Priority Tools (20 total):**
1. **File Management:** read_file, write_file, search_files, list_directory, delete_file
2. **Browser Automation:** navigate, fill_form, click_element, scrape_page, screenshot_element
3. **Communication:** send_email, read_email, create_calendar_event, search_calendar
4. **Developer:** execute_terminal, git_status, git_commit, git_push, search_code

**Implementation Pattern (for each tool):**
1. Write tool definition in `backend/tools/registry.py` TOOL_DEFINITIONS
2. Create tool module (e.g., `backend/tools/files.py`)
3. Implement handler with error handling and validation
4. Write tests in `backend/tests/test_tools/test_files.py`
5. Update router to recognize tool category
6. Commit with message: `feat(tools): add {tool_name} capability`

### Phase 4: Developer Powers (Weeks 11-13)

**Focus Areas:**
- Secure code execution sandbox (Docker-based)
- Database query tools (PostgreSQL, SQLite, MongoDB)
- API testing tools (HTTP client, response validation)
- Code review assistant (static analysis, suggestions)

### Phase 5: Vision & Perception (Weeks 14-17)

**Capabilities:**
- OCR integration (Tesseract, EasyOCR)
- Screen content analysis
- Camera feed analysis
- Document understanding (PDF extraction, structure parsing)

### Phase 6: Proactive Intelligence (Weeks 18-21)

**Components:**
- Pattern recognition engine
- Predictive suggestion system
- Background workflow orchestrator
- Multi-step planner with dependency tracking

### Phase 7: HUD & Finishing (Weeks 22-26)

**Deliverables:**
- Enhanced React HUD with real-time visualizations
- Security hardening (encryption, audit logging)
- Comprehensive test suite (>80% coverage)
- API documentation (OpenAPI/Swagger)
- Deployment automation (Docker, CI/CD)
- User guide and developer docs

---

## API Integrations Needed

### Voice Services
- **Deepgram:** STT API key, configure streaming endpoint
- **ElevenLabs:** TTS API key, voice ID selection
- **Porcupine:** Access key for wake word

### LLM Providers
- **Anthropic:** API key for Claude models
- **Google:** API key for Gemini
- **Ollama:** Local installation, model downloads

### Tool APIs
- **OpenWeather:** API key for weather data
- **Alpha Vantage:** API key for stock prices
- **Home Assistant:** URL and long-lived access token
- **Spotify:** Client ID and secret (OAuth)
- **Google Calendar:** OAuth credentials
- **Gmail:** OAuth credentials

### Infrastructure
- **Redis:** Connection URL
- **Neo4j:** URI, username, password
- **Chroma:** Persistent storage path

---

## Security Checklist

- [ ] Enable SQLCipher for SQLite encryption
- [ ] Implement JWT authentication for WebSocket
- [ ] Add tool-level permission system
- [ ] Create audit logging for all tool executions
- [ ] Implement code execution sandboxing (Docker)
- [ ] Enable TLS for all network connections
- [ ] Add API key rotation mechanism
- [ ] Implement rate limiting per session
- [ ] Add input validation and sanitization
- [ ] Create security incident response procedures

---

## Performance Targets

- **Voice latency:** <450ms perceived
- **Tool execution:** <2s for simple tools, <10s for complex
- **Memory retrieval:** <50ms for context assembly
- **WebSocket throughput:** >1000 messages/second
- **Memory usage:** <500MB baseline, <2GB under load

---

## Success Criteria

- ✅ Voice conversation feels natural (<450ms latency)
- ✅ All 47 capabilities implemented and tested
- ✅ 8 agent modules operational with clear boundaries
- ✅ 6-layer memory architecture fully functional
- ✅ Security framework with encryption and audit logging
- ✅ Test coverage >80%
- ✅ Documentation complete (API, architecture, user guide)
- ✅ Deployable via single Docker Compose command

---

**Plan complete. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach would you like to use?**
