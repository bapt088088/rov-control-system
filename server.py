import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

# --- GESTION DES CONNEXIONS (Manager) ---
class ConnectionManager:
    def __init__(self):
        # Liste de tous les navigateurs connectés
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"Nouveau pilote connecté. Total : {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"Connexion perdue. Restants : {len(self.active_connections)}")

    async def broadcast(self, message: str):
        # Envoie le message à absolument tout le monde
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Si une connexion est morte, on l'ignore
                pass

manager = ConnectionManager()

# --- SERVICE DES FICHIERS FRONTEND ---
# On dit à FastAPI que ton dossier 'frontend' contient index.html et jsmpeg.min.js
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def get():
    with open("frontend/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# --- WEBSOCKET UNIQUE (Télémétrie + Chat) ---
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # On attend des données du navigateur (comme un message de chat)
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # LOGIQUE DU CHAT
            if message_data.get("type") == "chat":
                print(f"Message reçu : {message_data['message']}")
                # On renvoie le message à tout le monde
                broadcast_data = {
                    "type": "chat",
                    "message": message_data["message"]
                }
                await manager.broadcast(json.dumps(broadcast_data))

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# --- SIMULATION DE TÉLÉMÉTRIE (Pour test) ---
# Dans ton vrai code, cette partie sera remplacée par la lecture de tes capteurs Raspberry Pi
async def simulate_rov_data():
    while True:
        # On fabrique des données de test
        telemetry = {
            "telemetry": {
                "amps": 1.25,
                "temperature": 24,
                "pressure": 1013,
                "posX": 0.5,
                "posY": -0.2,
                "leak": False,
                "obs_up": False,
                "obs_f_mid": False
            }
        }
        await manager.broadcast(json.dumps(telemetry))
        await asyncio.sleep(1) # Envoi toutes les secondes

@app.on_event("startup")
async def startup_event():
    # Lance la simulation ou la lecture des capteurs en arrière-plan
    asyncio.create_task(simulate_rov_data())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
