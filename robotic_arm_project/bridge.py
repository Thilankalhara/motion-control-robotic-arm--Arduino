"""
=============================================================
  Robotic Arm Gesture Control — Python Bridge v1.1
=============================================================
  This script does THREE things at once:
    1. Serves the HTML control panel on http://localhost:8000
    2. Runs a WebSocket server so the panel can send commands
    3. Forwards those commands to Arduino over USB serial

  HOW TO RUN:
    python bridge.py

  Then open Chrome and go to:
    http://localhost:8000/control_panel.html
=============================================================
"""

import serial
import serial.tools.list_ports
import time
import threading
import asyncio
import websockets
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import socket

# ─────────────────────────────────────────────────────────────
#  SETTINGS — COM7 auto-detected for your machine
# ─────────────────────────────────────────────────────────────
SERIAL_PORT = "COM7"          # Windows  →  COM3, COM4, COM7 ...
# SERIAL_PORT = "/dev/ttyUSB0"    # Linux    →  check with: ls /dev/tty*
# SERIAL_PORT = "/dev/tty.usbmodem101"  # Mac  →  check with: ls /dev/tty.*

BAUD_RATE  = 9600
WS_PORT    = 8765
HTTP_PORT  = 8000
# ─────────────────────────────────────────────────────────────

arduino    = None
last_cmd   = ""
ws_clients = set()

# ── PORT CONFLICT KILLER ──────────────────────────────────────
def kill_port(port):
    """Kill any process already using the given TCP port."""
    import subprocess, sys
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if parts and parts[-1].isdigit():
                pid = parts[-1]
                subprocess.run(f'taskkill /PID {pid} /F', shell=True,
                               capture_output=True)
                print(f"[INIT] Killed old process on port {port} (PID {pid})")
    except Exception:
        pass

# ── ARDUINO ───────────────────────────────────────────────────
def find_arduino():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        desc = p.description or ""
        dev  = p.device or ""
        if any(k in desc for k in ["Arduino", "CH340", "CH341", "FTDI"]) \
           or "usbmodem" in dev or "usbserial" in dev:
            return p.device
    return None

def connect_arduino():
    global arduino
    for attempt_port in [SERIAL_PORT, find_arduino()]:
        if not attempt_port:
            continue
        try:
            arduino = serial.Serial(attempt_port, BAUD_RATE, timeout=1)
            time.sleep(2)
            reply = arduino.readline().decode(errors="ignore").strip()
            print(f"[SERIAL] Connected on {attempt_port}  |  Arduino says: {reply or '(ready)'}")
            return True
        except serial.SerialException as e:
            print(f"[SERIAL] Could not open {attempt_port} — {e}")

    print("[SERIAL] No Arduino found. Running in demo mode (panel still works).")
    return False

def send_to_arduino(cmd):
    global last_cmd, arduino
    cmd = cmd.strip()
    if not cmd or cmd == last_cmd:
        return
    last_cmd = cmd
    if arduino and arduino.is_open:
        try:
            arduino.write((cmd + "\n").encode())
            print(f"  → Arduino: {cmd}")
        except Exception as e:
            print(f"[SERIAL] Write error: {e}")
    else:
        print(f"  [DEMO] Would send: {cmd}")

def read_arduino_replies():
    while True:
        try:
            if arduino and arduino.is_open and arduino.in_waiting:
                reply = arduino.readline().decode(errors="ignore").strip()
                if reply:
                    print(f"  ← Arduino: {reply}")
        except Exception:
            pass
        time.sleep(0.01)

# ── WEBSOCKET SERVER ──────────────────────────────────────────
async def ws_handler(websocket):
    ws_clients.add(websocket)
    print(f"[WS] Panel connected from {websocket.remote_address}")
    try:
        async for message in websocket:
            send_to_arduino(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        ws_clients.discard(websocket)
        print("[WS] Panel disconnected")

async def run_websocket():
    print(f"[WS] WebSocket server on ws://localhost:{WS_PORT}")
    async with websockets.serve(ws_handler, "localhost", WS_PORT):
        await asyncio.Future()

# ── HTTP SERVER ───────────────────────────────────────────────
class SilentHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

def run_http():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("localhost", HTTP_PORT), SilentHandler)
    print(f"[HTTP] Serving files on http://localhost:{HTTP_PORT}")
    print(f"[HTTP] Open Chrome → http://localhost:{HTTP_PORT}/control_panel.html")
    server.serve_forever()

# ── MAIN ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  Robotic Arm Gesture Control — Bridge v1.1")
    print("=" * 55)

    # Kill any leftover processes on our ports before starting
    print("[INIT] Clearing ports 8765 and 8000...")
    kill_port(WS_PORT)
    kill_port(HTTP_PORT)
    time.sleep(1)

    connect_arduino()

    threading.Thread(target=run_http, daemon=True).start()
    threading.Thread(target=read_arduino_replies, daemon=True).start()

    try:
        asyncio.run(run_websocket())
    except KeyboardInterrupt:
        print("\n[BRIDGE] Stopped by user.")
        if arduino and arduino.is_open:
            arduino.close()