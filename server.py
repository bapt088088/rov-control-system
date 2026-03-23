import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List

app = FastAPI()

# Pour afficher ton site web
if os.path.exists("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def get():
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "frontend", "index.html")
    with open(file_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

# ==========================================
# RELAIS TÉLÉMÉTRIE (Capteurs + Moteur)
# ==========================================
telemetry_clients: List[WebSocket] = []

@app.websocket("/ws")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    telemetry_clients.append(websocket)
    try:
        while True:
            # Reçoit le texte (JSON) de la Raspberry Pi
            data = await websocket.receive_text()
            
            # Renvoie les données à tous les navigateurs connectés
            for client in telemetry_clients:
                if client != websocket: # On ne renvoie pas à la Pi elle-même
                    try:
                        await client.send_text(data)
                    except:
                        pass
    except WebSocketDisconnect:
        telemetry_clients.remove(websocket)
    except Exception:
        if websocket in telemetry_clients:
            telemetry_clients.remove(websocket)

# ==========================================
# RELAIS VIDÉO (Caméra)
# ==========================================
video_clients: List[WebSocket] = []

@app.websocket("/ws/video")
async def ws_video(websocket: WebSocket):
    await websocket.accept()
    video_clients.append(websocket)
    try:
        while True:
            # Reçoit les images (Bytes) de la Raspberry Pi
            data = await websocket.receive_bytes()
            
            # Renvoie la vidéo à tous les navigateurs connectés
            for client in video_clients:
                if client != websocket:
                    try:
                        await client.send_bytes(data)
                    except:
                        pass
    except WebSocketDisconnect:
        video_clients.remove(websocket)
    except Exception:
        if websocket in video_clients:
            video_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
