import json
import asyncio
import os # Ajouté pour détecter le port de Render
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
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

# Vérifie que le dossier existe avant de monter pour éviter un crash au démarrage
if os.path.exists("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def get():
    # Utilisation d'un chemin relatif robuste
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "frontend", "index.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

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
        print(f"Erreur WebSocket: {e}")
        manager.disconnect(websocket)

async def send_real_telemetry(data_dict):
    message = json.dumps({"telemetry": data_dict})
    await manager.broadcast(message)

# --- INDISPENSABLE POUR RENDER ET LE LANCEMENT LOCAL ---
if __name__ == "__main__":
    import uvicorn
    # Render définit une variable d'environnement PORT, on l'utilise par défaut (8000 sinon)
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
