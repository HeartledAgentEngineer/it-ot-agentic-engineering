import os
import sys
import json
import time
import urllib.request

def get_api_key():
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        return api_key

    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                val, _ = winreg.QueryValueEx(key, "GEMINI_API_KEY")
                if val:
                    return val
        except Exception:
            pass

    return None

def main():
    api_key = get_api_key()
    if not api_key:
        print("Fehler: GEMINI_API_KEY ist nicht in den Umgebungsvariablen gesetzt!", file=sys.stderr)
        sys.exit(1)

    input_text = ""
    if len(sys.argv) > 1:
        files_content = []
        for arg in sys.argv[1:]:
            if os.path.isfile(arg):
                try:
                    with open(arg, 'r', encoding='utf-8') as f:
                        files_content.append(f"--- FILE: {arg} ---\n" + f.read())
                except Exception as e:
                    print(f"Warnung: konnte Datei {arg} nicht lesen: {e}", file=sys.stderr)
            else:
                files_content.append(arg)
        input_text = "\n\n".join(files_content)
    elif not sys.stdin.isatty():
        input_text = sys.stdin.read()

    if not input_text.strip():
        print("Fehler: Kein Code oder Git-Diff zum Prüfen übergeben.", file=sys.stderr)
        sys.exit(1)

    system_instruction = """
Du bist ein strenger, unvoreingenommener Code-Reviewer ("Critic").
Deine Aufgabe ist ein unnachgiebiges Audit des übergebenen Codes/Diffs.

Prüfe den Code auf:
1. KRITISCHE Sicherheitslücken (SQL Injection, XSS, Secret-Leaks, Remote Code Execution)
2. Absturzrisiken & Null-Pointer (Missing Checks, Uncaught Exceptions)
3. Logikfehler & Race Conditions
4. Performanz- & Architekturprobleme

Formatvorgabe für deine Antwort:
- Sortiert nach Schweregrad: [KRITISCH], [HOCH], [MITTEL], [NIEDRIG]
- Exakte Pfad- und Zeilenangaben (falls vorhanden)
- Konkreter, minimaler Korrekturvorschlag je Punkt
- Sei präzise und verzichte auf Smalltalk oder Höflichkeitsfloskeln.
"""

    models = ["gemini-2.0-flash", "gemini-2.0-flash-lite"]
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": system_instruction},
                    {"text": f"Hier ist der zu prüfende Code / Git-Diff:\n\n{input_text}"}
                ]
            }
        ]
    }

    last_error = None
    for model_name in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    review_output = result["candidates"][0]["content"]["parts"][0]["text"]
                    print(review_output)
                    return
            except urllib.error.HTTPError as e:
                last_error = f"Model {model_name} HTTP {e.code}: {e.reason}"
                if e.code == 429:
                    time.sleep(2)
                    continue
                else:
                    break
            except Exception as e:
                last_error = f"Model {model_name}: {str(e)}"
                break

    print(f"API-Fehler beim Aufruf von Gemini: {last_error}", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
