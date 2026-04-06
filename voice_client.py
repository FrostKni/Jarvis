"""
Local voice client: wake word → STT → WebSocket → backend → TTS playback.
Run this on the local machine alongside or separately from the FastAPI server.
"""
import asyncio
import json
import uuid
import websockets
from backend.voice.wake_word import WakeWordDetector
from backend.voice.stt import StreamingSTT
from backend.voice.tts import StreamingTTS

SESSION_ID = str(uuid.uuid4())
WS_URL = f"ws://localhost:8000/ws/voice/{SESSION_ID}"

tts = StreamingTTS()
stt: StreamingSTT | None = None
ws_conn = None
listening = False


async def on_final_transcript(text: str):
    global listening
    if not text.strip():
        return
    print(f"[You] {text}")
    if ws_conn:
        await ws_conn.send(json.dumps({"type": "transcript", "text": text}))
    listening = False
    if stt:
        await stt.stop()


async def on_partial_transcript(text: str):
    print(f"\r[...] {text}", end="", flush=True)


def on_wake_word():
    global listening, stt
    if listening:
        return
    print("\n[Jarvis] Listening...")
    listening = True
    asyncio.get_event_loop().create_task(start_stt())


async def start_stt():
    global stt
    stt = StreamingSTT(on_transcript=on_partial_transcript, on_final=on_final_transcript)
    await stt.start()


async def receive_responses(ws):
    async for raw in ws:
        msg = json.loads(raw)
        if msg["type"] == "done":
            print(f"\n[Jarvis] {msg['text']}")
        elif msg["type"] == "alert":
            print(f"\n[Jarvis ALERT] {msg['text']}")
            await tts.speak(msg["text"])
        elif msg["type"] == "thinking":
            print("\n[Jarvis] Thinking...", end="", flush=True)


async def main():
    global ws_conn
    detector = WakeWordDetector(on_detected=on_wake_word)
    detector.start()
    print("[Jarvis] Ready. Say 'Hey Jarvis' to activate.")

    async with websockets.connect(WS_URL) as ws:
        ws_conn = ws
        await receive_responses(ws)


if __name__ == "__main__":
    asyncio.run(main())
