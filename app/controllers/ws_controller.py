import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.models.schemas import Metadata
import asyncio
from app.containers.service_container import hfp_service, media_service

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/spotify-metadata")
async def websocket_spotify_metadata(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            metadata = media_service.get_spotify_metadata()
            if isinstance(metadata, Metadata):
                await websocket.send_text(metadata.model_dump_json())
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("📡 WebSocket bağlantısı kesildi.")

@router.websocket("/phone-data")
async def call_websocket(websocket: WebSocket):
    await websocket.accept()
    print("🔗 WebSocket bağlantısı kabul edildi")

    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, hfp_service.start_call_monitoring)
    try:
        while True:
            status = hfp_service.get_call_status()
            await websocket.send_text(json.dumps(status))
            await asyncio.sleep(3)
    except Exception as e:
        print(f"❌ WebSocket bağlantısı kesildi: {e}")

