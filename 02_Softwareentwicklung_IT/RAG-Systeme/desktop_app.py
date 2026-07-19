# ==============================================================================
# Script      : desktop_app.py
# Author      : Sebastian
# Date        : 2026-07-12
# Description : Native Windows-Desktop-App für das RAG-System. Startet den
#               FastAPI-Server im Hintergrund und öffnet ein WebView2-Fenster.
# ==============================================================================

import os
import sys
import time
import threading
import uvicorn
import webview
from main import app

def start_server():
    # Startet den RAG FastAPI-Server lokal auf Port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

if __name__ == '__main__':
    # 1. Starte den FastAPI-Server in einem Hintergrund-Thread (Daemon)
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 2. Kurze Pause, um dem Server Zeit zum Hochfahren zu geben
    time.sleep(1.2)
    
    # 3. Öffne ein natives, rahmenloses und ästhetisch passendes Desktop-Fenster
    webview.create_window(
        title="RAG Wissensassistent",
        url="http://127.0.0.1:8000",
        width=1280,
        height=850,
        min_size=(900, 600),
        background_color="#0f172a"  # Dunkelblau passend zu unserem Design
    )
    
    # 4. Starte das GUI-Fenster (unter Windows wird automatisch WebView2/Edge geladen)
    webview.start()
