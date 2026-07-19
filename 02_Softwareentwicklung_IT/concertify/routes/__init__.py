"""
routes/__init__.py
====================
Flask Blueprints — Routen gruppiert nach Domain.

Engineering-Konzept: "Flask Blueprint"
    Ein Blueprint ist eine Sammlung von Routen die separat definiert
    und dann an die App "angeheftet" wird. Wie ein eigener Sub-Modul
    der seine eigenen Routen mitbringt.

    In Frameworks wie ASP.NET nennt man das "Controller".
"""

from routes.imports import imports_bp
from routes.playlists import playlists_bp
from routes.songs import songs_bp

__all__ = ["imports_bp", "playlists_bp", "songs_bp"]
