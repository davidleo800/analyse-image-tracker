import sys
import time
import requests
import easyocr
import mss
import threading

import ollama

from PIL import Image

from pynput import keyboard

from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import (
    Qt,
    QRect,
    QPoint,
    QObject,
    QEvent
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen
)

# =========================================================
# CONFIG
# =========================================================

# DEEPSEEK_API_KEY = ""

TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

MODEL = "deepseek-chat"

HOTKEY_CHAR = "q"

# =========================================================
# OCR
# =========================================================

print("Cargando OCR...")

reader = easyocr.Reader(['es', 'en'])
# reader = easyocr.Reader(
#     ['es', 'en'],
#     gpu=True
# )

print("OCR listo")

# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(message):

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{TELEGRAM_BOT_TOKEN}/sendMessage"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        }

        requests.post(
            url,
            json=payload,
            timeout=30
        )

    except Exception as e:

        print("ERROR TELEGRAM:", e)


def send_telegram_image(path):

    try:

        url = (
            f"https://api.telegram.org/bot"
            f"{TELEGRAM_BOT_TOKEN}/sendPhoto"
        )

        with open(path, "rb") as img:

            requests.post(
                url,
                data={
                    "chat_id": TELEGRAM_CHAT_ID
                },
                files={
                    "photo": img
                }
            )

    except Exception as e:

        print(
            "ERROR TELEGRAM IMAGE:",
            e
        )
# =========================================================
# DEEPSEEK
# =========================================================


def ask_deepseek(text):

    response = ollama.chat(
        model='qwen2.5:3b',
        messages=[
            {
                'role': 'system',
                'content': (
                    'Responde claro y corto. '
                    'Si es programación, '
                    'da la solución directamente.'
                )
            },
            {
                'role': 'user',
                'content': text
            }
        ]
    )

    return response['message']['content']

# =========================================================
# SCREENSHOT
# =========================================================

import os
from datetime import datetime

def capture_region(x1, y1, x2, y2):
    print("ENTRANDO A CAPTURE_REGION")
    left = min(x1, x2)
    top = min(y1, y2)

    width = abs(x2 - x1)
    height = abs(y2 - y1)

    print(
        f"CAPTURE WIDTH={width} HEIGHT={height}"
    )

    if width < 10 or height < 10:

        print("REGIÓN INVÁLIDA")

        return None

    os.makedirs(
        "captures",
        exist_ok=True
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    path = (
        f"captures/capture_{timestamp}.png"
    )

    with mss.mss() as sct:

        monitor = {
            "left": left,
            "top": top,
            "width": width,
            "height": height
        }

        screenshot = sct.grab(monitor)

        img = Image.frombytes(
            "RGB",
            screenshot.size,
            screenshot.rgb
        )

        img.save(path)

    print(f"IMAGEN GUARDADA: {path}")

    return path

# =========================================================
# OCR
# =========================================================

def extract_text(image_path):

    results = reader.readtext(image_path)

    text = "\n".join(
        [r[1] for r in results]
    )

    return text

# =========================================================
# PROCESS FLOW
# =========================================================

def process_capture(x1, y1, x2, y2):

    print("THREAD INICIADO")

    global capture_in_progress

    try:

        capture_in_progress = True

        print("Capturando región...")

        image_path = capture_region(
            x1,
            y1,
            x2,
            y2
        )

        if not image_path:

            print("Captura inválida")

            return

        send_telegram_image(image_path)

        print("Extrayendo texto...")

        text = extract_text(image_path)

        print("\n========== TEXTO ==========\n")
        print(text)

        if not text.strip():

            send_telegram(
                "No se detectó texto."
            )

            return

        print("\nConsultando modelo...\n")

        answer = ask_deepseek(text)

        print(answer)

        send_telegram(answer)

        print("\nRespuesta enviada.\n")

    except Exception as e:

        print("ERROR:", e)

        send_telegram(f"ERROR: {e}")

    finally:

        capture_in_progress = False

# =========================================================
# OVERLAY
# =========================================================

class Overlay(QWidget):

    def __init__(self):

        super().__init__()

        self.start = None
        self.end = None

        self.dragging = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )

        self.setWindowOpacity(0.01)

        self.setMouseTracking(True)

        self.setCursor(
            Qt.CursorShape.CrossCursor
        )

        self.showFullScreen()

        self.setFocus()

        self.grabKeyboard()

        self.grabMouse()

        self.raise_()

        self.activateWindow()

        print("OVERLAY ACTIVO")

    def paintEvent(self, event):

        if not self.dragging:
            return

        painter = QPainter(self)

        pen = QPen(
            QColor(255, 255, 255, 180),
            2
        )

        painter.setPen(pen)

        rect = QRect(
            self.start,
            self.end
        )

        painter.drawRect(rect)

    def mousePressEvent(self, event):

        if event.button() == Qt.MouseButton.LeftButton:

            self.start = event.pos()

            self.end = self.start

            self.dragging = True

            print(
                "MOUSE DOWN:",
                self.start.x(),
                self.start.y()
            )

            self.update()

    def mouseMoveEvent(self, event):

        if self.dragging:

            self.end = event.pos()

            print(
                "MOVE:",
                self.end.x(),
                self.end.y()
            )

            self.update()

    def mouseReleaseEvent(self, event):

        if event.button() != Qt.MouseButton.LeftButton:
            return

        self.end = event.pos()

        print(
            "MOUSE UP:",
            self.end.x(),
            self.end.y()
        )

        self.finish_capture()

    def finish_capture(self):

        x1 = self.start.x()
        y1 = self.start.y()

        x2 = self.end.x()
        y2 = self.end.y()

        width = abs(x2 - x1)
        height = abs(y2 - y1)

        print(
            f"WIDTH={width}, HEIGHT={height}"
        )

        self.dragging = False

        if width < 10 or height < 10:

            print("Selección demasiado pequeña")

            self.close()

            return
        
        self.releaseMouse()
        self.hide()

        QApplication.processEvents()

        self.close()

        QApplication.processEvents()

        print("INICIANDO THREAD OCR/LLM")

        thread = threading.Thread(
            target=process_capture,
            args=(x1, y1, x2, y2),
            daemon=True
        )

        thread.start()

        self.releaseKeyboard()
        self.releaseMouse()

# =========================================================
# QT EVENT BRIDGE
# =========================================================

EVENT_TYPE = QEvent.Type(
    QEvent.registerEventType()
)

class ShowOverlayEvent(QEvent):

    def __init__(self):

        super().__init__(EVENT_TYPE)

# =========================================================
# EVENT FILTER
# =========================================================

class EventFilter(QObject):

    def eventFilter(
        self,
        obj,
        event
    ):

        global overlay

        if event.type() == EVENT_TYPE:

            print("CREANDO OVERLAY")

            overlay = Overlay()

            return True

        return False

# =========================================================
# QT APP
# =========================================================

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)
main_widget = QWidget()
main_widget.hide()
overlay = None
capture_in_progress = False

event_filter = EventFilter()

app.installEventFilter(event_filter)

# =========================================================
# KEYBOARD LISTENER
# =========================================================

pressed_keys = set()

overlay_open = False

def key_to_str(key):

    try:

        if hasattr(key, "char") and key.char:
            return key.char.lower()

        return str(key)

    except:
        return str(key)

def hotkey_active():

    alt = (
        "Key.alt_l" in pressed_keys or
        "Key.alt_r" in pressed_keys
    )

    x = "x" in pressed_keys

    return alt and x

def on_press(key):

    global overlay_open
    global capture_in_progress

    if capture_in_progress:
        return

    k = key_to_str(key)

    pressed_keys.add(k)

    print("PRESS:", k)

    if hotkey_active():

        if not overlay_open:

            overlay_open = True

            print("HOTKEY DETECTADA")

            QApplication.instance().postEvent(
                app,
                ShowOverlayEvent()
            )

def on_release(key):

    global overlay_open

    k = key_to_str(key)

    try:
        pressed_keys.remove(k)
    except:
        pass

    print("RELEASE:", k)

    if not hotkey_active():

        overlay_open = False

listener = keyboard.Listener(
    on_press=on_press,
    on_release=on_release
)

listener.start()

# =========================================================
# START
# =========================================================

print(
    "\nApp iniciada.\n"
    "Mantén CTRL + SHIFT + Q\n"
    "y arrastra para seleccionar.\n"
)

sys.exit(app.exec())