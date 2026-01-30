# server.py
from fastapi import FastAPI, WebSocket, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
import asyncio
import uvicorn
from datetime import datetime

app = FastAPI()

# Configuration de la sécurité
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "une-cle-super-secrete"))
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

video_clients = set()
connected_websockets = []

@app.get("/")
async def root():
    return RedirectResponse("/dashboard")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <html>
        <body style="font-family:Arial; text-align:center; padding-top:100px; background:#1a1a1a; color:white;">
            <h2>🔐 ROV Public Access</h2>
            <form method="post"><input type="password" name="password" style="padding:10px;"/><br><br>
            <button type="submit" style="padding:10px 20px;">Connexion</button></form>
        </body>
    </html>
    """

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    # On utilise une variable d'environnement pour le mot de passe sur Render
    if password == os.environ.get("DASHBOARD_PASSWORD", "roboti129-AA"):
        request.session["authenticated"] = True
        return RedirectResponse("/dashboard", status_code=302)
    return HTMLResponse("❌ Incorrect", status_code=401)

@app.get("/dashboard")
async def dashboard(request: Request):
    if not request.session.get("authenticated"):
        return RedirectResponse("/login")
    return FileResponse(os.path.join("frontend", "index.html"))

@app.websocket("/ws/video")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    video_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_bytes()
            # Diffusion aux autres clients
            for client in list(video_clients):
                if client != websocket:
                    try:
                        await asyncio.wait_for(client.send_bytes(data), timeout=0.05)
                    except:
                        if client in video_clients: video_clients.remove(client)
    except:
        pass
    finally:
        if websocket in video_clients: video_clients.remove(websocket)

if __name__ == "__main__":
    # Render définit automatiquement la variable d'environnement PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)