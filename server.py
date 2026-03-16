import json
import asyncio
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = [] # Pour le texte (chat/télémétrie)
        self.video_connections: List[WebSocket] = []  # Pour la vidéo

    # --- Gestion des connexions TEXTE ---
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    # --- Gestion des connexions VIDÉO ---
    async def connect_video(self, websocket: WebSocket):
        await websocket.accept()
        self.video_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.video_connections:
            self.video_connections.remove(websocket)

    # --- Envoi de TEXTE ---
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

    # --- Envoi de VIDÉO (Bytes) ---
    async def broadcast_video(self, data: bytes):
        for connection in self.video_connections:
            try:
                await connection.send_bytes(data)
            except:
                pass

manager = ConnectionManager()

if os.path.exists("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def get():
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "frontend", "index.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# ==========================================
# 1. WEBSOCKET POUR LE CHAT ET LA TÉLÉMÉTRIE
# ==========================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            if message_data.get("type") == "chat":
                broadcast_data = {"type": "chat", "message": message_data["message"]}
                await manager.broadcast(json.dumps(broadcast_data))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Erreur WebSocket Texte: {e}")
        manager.disconnect(websocket)

# ==========================================
# 2. NOUVEAU : WEBSOCKET POUR LA VIDÉO
# ==========================================
@app.websocket("/ws/video")
async def video_endpoint(websocket: WebSocket):
    await manager.connect_video(websocket)
    try:
        while True:
            # On reçoit des octets (la vidéo du Streamer.py) et non du texte !
            data = await websocket.receive_bytes()
            # On renvoie ces octets à tous ceux qui sont connectés pour regarder
            await manager.broadcast_video(data)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Erreur WebSocket Vidéo: {e}")
        manager.disconnect(websocket)

async def send_real_telemetry(data_dict):
    message = json.dumps({"telemetry": data_dict})
    await manager.broadcast(message)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
