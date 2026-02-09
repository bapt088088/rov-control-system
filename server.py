# server.py
from fastapi import FastAPI, WebSocket, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import os
import asyncio
import uvicorn

app = FastAPI()

# 1. Configuration de la sécurité (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Gestion des sessions (nécessite 'itsdangerous' dans requirements.txt)
app.add_middleware(SessionMiddleware, secret_key="une-cle-tres-secrete-pour-le-rov")

# Servir les fichiers statiques (ton dossier frontend)
# Assure-toi que ton dossier se nomme bien 'frontend' sur GitHub
if os.path.exists("frontend"):
    app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

# Liste des clients connectés pour la vidéo
video_clients = set()

@app.get("/")
async def root():
    return RedirectResponse("/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <html>
        <head><title>ROV LOGIN</title></head>
        <body style="font-family:Arial; text-align:center; padding-top:100px; background:#0a0b10; color:white;">
            <div style="display:inline-block; padding:40px; border:1px solid #00f2ff; border-radius:10px; background:rgba(0,242,255,0.05);">
                <h2 style="color:#00f2ff;">🔐 Accès Pilote ROV</h2>
                <form method="post">
                    <input type="password" name="password" placeholder="Mot de passe" style="padding:12px; border-radius:5px; border:none; width:200px;"><br><br>
                    <button type="submit" style="padding:10px 25px; background:#00f2ff; border:none; border-radius:5px; cursor:pointer; font-weight:bold;">CONNEXION</button>
                </form>
            </div>
        </body>
    </html>
    """

@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    # --- MODIFICATION ICI ---
    # On définit le mot de passe en dur pour être sûr que ça fonctionne
    if password == "robotAA":
        print("✅ Connexion réussie")
        request.session["authenticated"] = True
        return RedirectResponse("/dashboard", status_code=303)
    
    print(f"❌ Tentative de connexion échouée avec : {password}")
    return HTMLResponse("<html><body style='background:#0a0b10; color:red; text-align:center; padding-top:50px;'><h2>❌ Mot de passe incorrect</h2><a href='/login' style='color:white;'>Réessayer</a></body></html>", status_code=401)

@app.get("/dashboard")
async def dashboard(request: Request):
    # Vérification si l'utilisateur est passé par le login
    if not request.session.get("authenticated"):
        return RedirectResponse("/login")
    
    # On renvoie ton fichier index.html situé dans le dossier frontend
    index_path = os.path.join("frontend", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h2>Erreur : Fichier index.html introuvable dans le dossier /frontend</h2>")

@app.websocket("/ws/video")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    video_clients.add(websocket)
    print(f"🎥 Nouveau client vidéo connecté. Total : {len(video_clients)}")
    
    try:
        while True:
            # Réception des données binaires de la Raspberry Pi
            data = await websocket.receive_bytes()
            
            # Diffusion immédiate à TOUS les autres clients (le dashboard)
            for client in list(video_clients):
                if client != websocket:
                    try:
                        await client.send_bytes(data)
                    except:
                        video_clients.remove(client)
    except Exception as e:
        print(f"ℹ️ Déconnexion WebSocket : {e}")
    finally:
        if websocket in video_clients:
            video_clients.remove(websocket)

# Démarrage du serveur
if __name__ == "__main__":
    # Render utilise la variable d'environnement PORT, sinon 8000 par défaut
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Serveur ROV démarré sur le port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
