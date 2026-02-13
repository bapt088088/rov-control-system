import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def get():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# --- WEBSOCKET POUR LE SITE WEB ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Rediffusion du CHAT
            if message_data.get("type") == "chat":
                broadcast_data = {"type": "chat", "message": message_data["message"]}
                await manager.broadcast(json.dumps(broadcast_data))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- FONCTION POUR ENVOYER TES VRAIES DONNÉES ---
# Appelle cette fonction depuis ton code de contrôle des capteurs
async def send_real_telemetry(data_dict):
    """
    Utilise cette fonction pour envoyer tes vraies données au site.
    Exemple de data_dict : {"amps": 2.1, "temperature": 18, ...}
    """
    message = json.dumps({"telemetry": data_dict})
    await manager.broadcast(message)
