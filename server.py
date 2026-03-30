import eventlet
eventlet.monkey_patch() # Requis pour que SocketIO gère bien les threads concurrents

from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import subprocess
import time
import serial
import pygame
import board
import adafruit_dht
import mpu6050
import os

app = Flask(__name__, template_folder='.') # Cherche index.html dans le même dossier
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- CONFIGURATIONS ---
PC_IP = "172.20.10.8"
ARDUINO_PORT = '/dev/ttyACM0'

# --- INITIALISATION DES COMPOSANTS (Avec gestion d'erreur pour ne pas tout crasher) ---
try:
    dht_device = adafruit_dht.DHT22(board.D4)
    print("Capteur DHT22 initialisé.")
except Exception as e:
    print(f"Erreur init DHT22: {e}")
    dht_device = None

try:
    sensor_mpu = mpu6050.mpu6050(0x68)
    print("Capteur MPU6050 initialisé.")
except Exception as e:
    print(f"Erreur init MPU6050: {e}")
    sensor_mpu = None

try:
    arduino = serial.Serial(ARDUINO_PORT, 9600)
    time.sleep(2)
    print("Arduino connecté.")
except Exception as e:
    print(f"Erreur init Arduino: {e}")
    arduino = None

# Variables globales MPU
offsets = {'ax': 0, 'ay': 0, 'az': 0, 'gx': 0, 'gy': 0, 'gz': 0}
GAUSS_GRAVITY = 9.80665

# --- FONCTIONS DE THREADS ---

def thread_camera():
    """Lance le flux vidéo sans enregistrement local et masque les logs."""
    print(f"--- DEMARRAGE VIDEO vers {PC_IP} ---")
    command = (
        f"rpicam-vid -t 0 --width 754 --height 480 --framerate 30 --bitrate 2000000 "
        f"--inline --intra 1 --flush "
        f"--codec libav --libav-format mpegts "
        f"-o - | "
        f"socat - UDP-SENDTO:{PC_IP}:5000"
    )
    # L'ajout de 2>/dev/null cache les logs INFO de la caméra
    subprocess.Popen(command + " 2>/dev/null", shell=True)

def thread_dht22():
    """Lit la température et l'humidité toutes les 2 secondes."""
    while True:
        if dht_device:
            try:
                temperature = dht_device.temperature
                humidity = dht_device.humidity
                if humidity is not None and temperature is not None:
                    # Envoi au site web via WebSocket
                    socketio.emit('dht_data', {'temp': round(temperature, 1), 'hum': round(humidity, 1)})
            except RuntimeError:
                pass # Erreur normale et fréquente avec le DHT22
            except Exception as e:
                pass
        socketio.sleep(2.0)

def thread_mpu6050():
    """Lit la position (Gyro/Accel) en continu."""
    while True:
        if sensor_mpu:
            try:
                a_raw = sensor_mpu.get_accel_data()
                g_raw = sensor_mpu.get_gyro_data()
                
                # Application des offsets (simplifié ici, tu peux rajouter ta fonction de calibration au démarrage si besoin)
                data = {
                    'ax': round(a_raw['x'] - offsets['ax'], 2),
                    'ay': round(a_raw['y'] - offsets['ay'], 2),
                    'az': round(a_raw['z'] - offsets['az'], 2),
                    'gx': round(g_raw['x'] - offsets['gx'], 2),
                    'gy': round(g_raw['y'] - offsets['gy'], 2),
                    'gz': round(g_raw['z'] - offsets['gz'], 2)
                }
                socketio.emit('mpu_data', data)
            except Exception as e:
                pass
        socketio.sleep(0.1) # 10 fois par seconde pour le web, c'est fluide

def thread_manette():
    """Gère la manette connectée en USB au Raspberry Pi."""
    # Variable d'environnement pour que pygame fonctionne sans écran connecté
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("Aucune manette détectée sur le Raspberry Pi.")
        return

    js = pygame.joystick.Joystick(0)
    js.init()
    print("Manette connectée au serveur. Prêt à piloter.")

    vitesse_actuelle = 1500
    PAS_ACCELERATION = 10

    while True:
        pygame.event.pump()
        y = -js.get_axis(1)

        if abs(y) < 0.1:
            y = 0

        vitesse_cible = int(1500 + y * 400)

        # Lissage
        if vitesse_actuelle < vitesse_cible:
            vitesse_actuelle = min(vitesse_actuelle + PAS_ACCELERATION, vitesse_cible)
        elif vitesse_actuelle > vitesse_cible:
            vitesse_actuelle = max(vitesse_actuelle - PAS_ACCELERATION, vitesse_cible)

        if arduino:
            try:
                arduino.write((str(vitesse_actuelle) + "\n").encode())
            except Exception as e:
                pass
        
        socketio.sleep(0.02) # 50Hz

# --- ROUTES WEB ---

@app.route('/')
def index():
    # S'assure que tes fichiers frontend.html ou index.html sont bien chargés
    return render_template('index.html') 

# --- DEMARRAGE DU SERVEUR ---

if __name__ == '__main__':
    print("Démarrage du système du ROV...")
    
    # Lancement de la vidéo
    thread_camera()
    
    # Lancement des tâches de fond (Threads)
    socketio.start_background_task(target=thread_dht22)
    socketio.start_background_task(target=thread_mpu6050)
    socketio.start_background_task(target=thread_manette)
    
    # Démarrage du serveur web sur le port 8080 (accessible depuis ton PC via l'IP du Pi)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
