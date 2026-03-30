import eventlet
eventlet.monkey_patch() # Indispensable pour que le web et le robot tournent en même temps

from flask import Flask, render_template
from flask_socketio import SocketIO
import subprocess
import time
import serial
import pygame
import board
import adafruit_dht
import mpu6050
import os

# --- INITIALISATION DU SERVEUR WEB ---
app = Flask(__name__, template_folder='.') # Cherche index.html dans le même dossier
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURATIONS ---
PC_IP = "172.20.10.8"
ARDUINO_PORT = '/dev/ttyACM0'
GAUSS_GRAVITY = 9.80665

# --- INITIALISATION MATERIELLE (Tolérance aux pannes) ---
print("--- INITIALISATION DES COMPOSANTS ---")

try:
    dht_device = adafruit_dht.DHT22(board.D4)
    print("[OK] Capteur Humidité (DHT22)")
except Exception as e:
    print(f"[ERREUR] DHT22: {e}")
    dht_device = None

try:
    sensor_mpu = mpu6050.mpu6050(0x68)
    print("[OK] Capteur Position (MPU6050)")
except Exception as e:
    print(f"[ERREUR] MPU6050: {e}")
    sensor_mpu = None

try:
    arduino = serial.Serial(ARDUINO_PORT, 9600)
    time.sleep(2)
    print("[OK] Arduino (Moteurs)")
except Exception as e:
    print(f"[ERREUR] Arduino: {e}")
    arduino = None


# --- LES SOUS-PROGRAMMES (Tâches de fond) ---

def start_camera():
    """Lance la vidéo vers le PC sans enregistrer, et cache les logs inutiles"""
    print(f"[INFO] Démarrage vidéo vers {PC_IP}...")
    command = (
        f"rpicam-vid -t 0 --width 754 --height 480 --framerate 30 --bitrate 2000000 "
        f"--inline --intra 1 --flush --codec libav --libav-format mpegts "
        f"-o - | socat - UDP-SENDTO:{PC_IP}:5000"
    )
    subprocess.Popen(command + " 2>/dev/null", shell=True)

def boucle_dht22():
    """Lit la température/humidité toutes les 2s"""
    while True:
        if dht_device:
            try:
                temp = dht_device.temperature
                hum = dht_device.humidity
                if hum is not None and temp is not None:
                    socketio.emit('dht_data', {'temp': round(temp, 1), 'hum': round(hum, 1)})
            except:
                pass # Ignore les petites erreurs normales du capteur
        socketio.sleep(2.0)

def boucle_mpu6050():
    """Lit la position en continu"""
    while True:
        if sensor_mpu:
            try:
                a = sensor_mpu.get_accel_data()
                g = sensor_mpu.get_gyro_data()
                data = {
                    'ax': round(a['x'], 2), 'ay': round(a['y'], 2), 'az': round(a['z'] - GAUSS_GRAVITY, 2),
                    'gx': round(g['x'], 2), 'gy': round(g['y'], 2), 'gz': round(g['z'], 2)
                }
                socketio.emit('mpu_data', data)
            except:
                pass
        socketio.sleep(0.1)

def boucle_manette():
    """Gère la manette et le pilotage des moteurs via l'Arduino"""
    os.environ["SDL_VIDEODRIVER"] = "dummy" # Requis sur Pi
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("[AVERTISSEMENT] Aucune manette détectée.")
        return

    js = pygame.joystick.Joystick(0)
    js.init()
    print("[OK] Manette prête.")

    vitesse_actuelle = 1500
    PAS_ACCELERATION = 10

    while True:
        pygame.event.pump()
        y = -js.get_axis(1)
        if abs(y) < 0.1: y = 0

        vitesse_cible = int(1500 + y * 400)

        if vitesse_actuelle < vitesse_cible:
            vitesse_actuelle = min(vitesse_actuelle + PAS_ACCELERATION, vitesse_cible)
        elif vitesse_actuelle > vitesse_cible:
            vitesse_actuelle = max(vitesse_actuelle - PAS_ACCELERATION, vitesse_cible)

        if arduino:
            try:
                arduino.write((str(vitesse_actuelle) + "\n").encode())
            except:
                pass
        
        socketio.sleep(0.02)

# --- ROUTE DU SITE WEB ---

@app.route('/')
def index():
    # Assure-toi que ton frontend s'appelle bien index.html
    return render_template('index.html') 

# --- LANCEMENT GLOBAL ---

if __name__ == '__main__':
    print("\n=== DEMARRAGE DU SYSTEME ROV ===")
    start_camera()
    
    # Lancement des threads
    socketio.start_background_task(target=boucle_dht22)
    socketio.start_background_task(target=boucle_mpu6050)
    socketio.start_background_task(target=boucle_manette)
    
    print(f"[INFO] Serveur Web prêt sur le port 8080.")
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
