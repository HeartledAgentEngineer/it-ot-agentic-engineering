"""
installer_lib – Installations-Logik für typeFREE.

Reine Funktionen, die das Batch-Skript `setup.cmd` aufruft.
So bleibt die Kernlogik testbar.
"""

import os
import json
import subprocess
import time


def create_env_file(
    pfad: str,
    openrouter_key: str = "",
    openai_key: str = "",
) -> str:
    """Erzeugt eine .env-Datei mit den API-Keys.

    Args:
        pfad: Zielpfad für die .env-Datei (inkl. .env).
        openrouter_key: OpenRouter API-Key.
        openai_key: OpenAI API-Key (optional).

    Returns:
        True, wenn die Datei geschrieben wurde.
    """
    zeilen = [
        "# typeFREE API-Keys",
        f"# Erstellt am {time.strftime('%d.%m.%Y um %H:%M')}",
        "",
        f"OPENROUTER_API_KEY={openrouter_key}",
        f"OPENAI_API_KEY={openai_key}",
        "",
    ]
    with open(pfad, 'w', encoding='utf-8') as f:
        f.write('\n'.join(zeilen))
    return True


def create_shortcut(ziel: str, verknuepfung: str, beschreibung: str = "") -> bool:
    """Erstellt eine Windows-Verknüpfung (.lnk) per PowerShell.

    Args:
        ziel: Pfad zur ausführbaren Datei.
        verknuepfung: Pfad zur .lnk-Datei.
        beschreibung: Anzeigetext für die Verknüpfung.

    Returns:
        True bei Erfolg, False bei Fehler.
    """
    if os.path.exists(verknuepfung):
        return True
    beschreibung = beschreibung or "typeFREE - Voice-to-Text"
    ordner = os.path.dirname(verknuepfung)
    if not os.path.exists(ordner):
        return False
    ps_code = (
        f"$WS = New-Object -ComObject WScript.Shell; "
        f"$SC = $WS.CreateShortcut('{verknuepfung}'); "
        f"$SC.TargetPath = '{ziel}'; "
        f"$SC.WorkingDirectory = '{os.path.dirname(ziel)}'; "
        f"$SC.Description = '{beschreibung}'; "
        f"$SC.Save()"
    )
    try:
        subprocess.run(
            ['powershell', '-Command', ps_code],
            capture_output=True, timeout=10, check=True,
        )
        return os.path.exists(verknuepfung)
    except Exception:
        return False


def remove_shortcut(verknuepfung: str) -> bool:
    """Entfernt eine Verknüpfung, falls vorhanden."""
    try:
        if os.path.exists(verknuepfung):
            os.remove(verknuepfung)
            return True
        return True
    except Exception:
        return False


def create_autostart_tasks(exe_pfad: str) -> int:
    """Erstellt beide Windows-Aufgaben für den Autostart.

    Aufgabe 1: Start bei Anmeldung (ONLOGON)
    Aufgabe 2: Start beim Aufwachen (ONEVENT Kernel-Power 107)

    Args:
        exe_pfad: Vollständiger Pfad zur typeFREE.exe.

    Returns:
        Anzahl der erfolgreich erstellten Aufgaben (0, 1 oder 2).
    """
    erledigt = 0

    # Aufgabe 1: Bei Anmeldung
    cmd1 = [
        'schtasks', '/Create', '/SC', 'ONLOGON',
        '/TN', 'typeFREE',
        '/TR', f'"{exe_pfad}" --autostart',
        '/RL', 'HIGHEST', '/F', '/IT',
    ]
    try:
        r1 = subprocess.run(cmd1, capture_output=True, timeout=15)
        if r1.returncode == 0:
            erledigt += 1
    except Exception:
        pass

    # Aufgabe 2: Beim Aufwachen
    cmd2 = [
        'schtasks', '/Create', '/SC', 'ONEVENT',
        '/EC', 'System',
        '/MO', '*[System[Provider[@Name=\'Microsoft-Windows-Kernel-Power\'] and EventID=107]]',
        '/TN', 'typeFREE-Aufwachen',
        '/TR', f'"{exe_pfad}" --autostart',
        '/RL', 'HIGHEST', '/F', '/IT',
    ]
    try:
        r2 = subprocess.run(cmd2, capture_output=True, timeout=15)
        if r2.returncode == 0:
            erledigt += 1
    except Exception:
        pass

    return erledigt


def remove_autostart_tasks() -> int:
    """Entfernt beide typeFREE-Aufgaben aus der Aufgabenplanung.

    Returns:
        Anzahl der entfernten Aufgaben (0, 1 oder 2).
    """
    entfernt = 0
    for name in ['typeFREE', 'typeFREE-Aufwachen']:
        try:
            r = subprocess.run(
                ['schtasks', '/Delete', '/TN', name, '/F'],
                capture_output=True, timeout=10,
            )
            if r.returncode == 0:
                entfernt += 1
        except Exception:
            pass
    return entfernt


def save_install_info(install_dir: str, autostart: bool = True) -> str:
    """Speichert Installations-Informationen in install.json.

    Args:
        install_dir: Installationsverzeichnis.
        autostart: Ob Autostart eingerichtet wurde.

    Returns:
        Pfad zur erstellten JSON-Datei.
    """
    info = {
        "install_dir": install_dir,
        "installed_at": time.strftime('%Y-%m-%d %H:%M'),
        "autostart": autostart,
    }
    pfad = os.path.join(install_dir, 'install.json')
    with open(pfad, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    return pfad


def read_install_info(install_dir: str) -> dict:
    """Liest die Installations-Info aus install.json.

    Args:
        install_dir: Installationsverzeichnis.

    Returns:
        Dict mit den gespeicherten Werten oder leeres Dict bei Fehler.
    """
    pfad = os.path.join(install_dir, 'install.json')
    try:
        with open(pfad, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}