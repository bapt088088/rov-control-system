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

app = Flask(__name__, template_folder='.')
# On enlève eventlet et on utilise threading par défaut
socketio = SocketIO(app, cors_allowed_origins="*")

PC_IP = "172.20.10.8"
ARDUINO_PORT = '/dev/ttyACM0'
GAUSS_GRAVITY = 9.80665

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
    print("[OK] Arduino (Moteurs)")
except Exception as e:
    arduino = None

def start_camera():
    command = (
        f"rpicam-vid -t 0 --width 754 --height 480 --framerate 30 --bitrate 2000000 "
        f"--inline --intra 1 --flush --codec libav --libav-format mpegts "
        f"-o - | socat - UDP-SENDTO:{PC_IP}:5000"
    )
    subprocess.Popen(command + " 2>/dev/null", shell=True)

def boucle_dht22():
    while True:
        if dht_device:
            try:
                temp = dht_device.temperature
                hum = dht_device.humidity
                if hum is not None and temp is not None:
                    socketio.emit('dht_data', {'temp': round(temp, 1), 'hum': round(hum, 1)})
            except Exception as e:
                print(f"[ERREUR DHT22] {e}") 
        socketio.sleep(2.0)

def boucle_mpu6050():
    compteur_test = 0
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
            except Exception as e:
                print(f"[ERREUR MPU6050] {e}") 
                compteur_test += 1
                socketio.emit('mpu_data', {'ax': compteur_test, 'ay': 9.9, 'az': 9.9})
        socketio.sleep(0.1)

def boucle_manette():
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    try:
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() > 0:
            js = pygame.joystick.Joystick(0)
            js.init()
            vitesse_actuelle = 1500
            while True:
                pygame.event.pump()
                y = -js.get_axis(1)
                if abs(y) < 0.1: y = 0
                vitesse_cible = int(1500 + y * 400)
                
                if vitesse_actuelle < vitesse_cible: vitesse_actuelle = min(vitesse_actuelle + 10, vitesse_cible)
                elif vitesse_actuelle > vitesse_cible: vitesse_actuelle = max(vitesse_actuelle - 10, vitesse_cible)
                
                if arduino: arduino.write((str(vitesse_actuelle) + "\n").encode())
                socketio.sleep(0.02)
        else:
            return
    except:
        pass

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    start_camera()
    socketio.start_background_task(target=boucle_dht22)
    socketio.start_background_task(target=boucle_mpu6050)
    socketio.start_background_task(target=boucle_manette)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)
