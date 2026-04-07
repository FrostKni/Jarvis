import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.brain.llm import LLMClient
from backend.brain.router import IntentRouter
from backend.brain.orchestrator import JarvisOrchestrator
from backend.memory.vector import VectorMemory
from backend.memory.graph import GraphMemory
from backend.memory.store import PersistentStore
from backend.memory.session import SessionCache
from backend.memory.assembler import MemoryAssembler
from backend.memory.procedural import ProceduralMemory
from backend.memory.world_model import WorldModel
from backend.tools.registry import ToolExecutor
from backend.voice.tts import StreamingTTS
from agents.proactive import ProactiveAgent

settings = get_settings()

llm = LLMClient()
router = IntentRouter()
vector = VectorMemory()
graph = GraphMemory()
store = PersistentStore()
session_cache = SessionCache()
procedural = ProceduralMemory(store=store)
world_model = WorldModel(store=store)
assembler = MemoryAssembler(vector, graph, store, procedural, world_model)
executor = ToolExecutor(store)
orchestrator = JarvisOrchestrator(
    llm, router, assembler, session_cache, vector, executor, procedural, world_model
)
tts = StreamingTTS()

active_connections: dict[str, WebSocket] = {}


async def _on_proactive_alert(text: str):
    """Broadcast proactive alerts to all connected clients."""
    for ws in list(active_connections.values()):
        try:
            await ws.send_json({"type": "alert", "text": text})
            await tts.speak(text)
        except Exception:
            pass


proactive = ProactiveAgent(store, session_cache, _on_proactive_alert)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init()
    await session_cache.connect()
    await procedural.load()
    proactive.start()
    yield
    proactive.stop()
    await session_cache.close()
    await graph.close()


app = FastAPI(title="Jarvis API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/voice/{session_id}")
async def voice_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)

            if msg["type"] == "transcript":
                user_text = msg["text"]
                await websocket.send_json({"type": "thinking"})

                full_response = ""
                async for token in orchestrator.process(session_id, user_text):
                    full_response += token
                    await websocket.send_json({"type": "token", "text": token})

                await websocket.send_json({"type": "done", "text": full_response})
                await tts.speak(full_response)

            elif msg["type"] == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        active_connections.pop(session_id, None)


@app.websocket("/ws/hud/{session_id}")
async def hud_endpoint(websocket: WebSocket, session_id: str):
    """Dedicated WebSocket for HUD status updates."""
    await websocket.accept()
    pubsub = await session_cache.subscribe(f"hud:{session_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass


@app.get("/health")
async def health():
    return {"status": "online", "mode": "local" if settings.local_mode else "cloud"}


@app.post("/api/preference")
async def set_preference(key: str, value: str):
    await store.set_preference(key, value)
    return {"ok": True}


@app.get("/api/preferences")
async def get_preferences():
    return await store.get_all_preferences()
