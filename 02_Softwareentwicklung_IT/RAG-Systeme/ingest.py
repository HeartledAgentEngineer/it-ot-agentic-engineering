# ==============================================================================
# Script      : ingest.py
# Author      : Sebastian
# Date        : 2026-07-11
# Version     : 1.0
# Description : Konvertiert PDF-Dateien via Mistral OCR in Markdown, berechnet
#               Mistral-Embeddings und speichert Chunks in Supabase.
# ==============================================================================

import os
import sys
import hashlib
import json
import requests
import psycopg2
from dotenv import load_dotenv
import google.generativeai as genai

# .env laden
load_dotenv()

# API Keys und DB-Verbindung konfigurieren
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SUPABASE_CONNECTION_STRING = os.getenv("SUPABASE_CONNECTION_STRING")
PCLOUD_USERNAME = os.getenv("PCLOUD_USERNAME")
PCLOUD_PASSWORD = os.getenv("PCLOUD_PASSWORD")

PCLOUD_DOCS_DIR = r"P:\RAG_Documents"

# Gemini API konfigurieren
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def get_file_hash(file_path):
    """Berechnet den MD5-Hash einer Datei, um doppelte Ingestierung zu vermeiden."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        buf = f.read(65536)
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def check_if_already_ingested(file_hash):
    """Prüft, ob eine Datei mit demselben Hash bereits in Supabase existiert."""
    if not SUPABASE_CONNECTION_STRING:
        return False
    try:
        conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM documents 
            WHERE (metadata->>'file_hash') = %s 
            LIMIT 1;
        """, (file_hash,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result is not None
    except Exception as e:
        print(f"Warnung bei Hash-Überprüfung: {e}")
        return False

def delete_file_from_db(file_name):
    """Löscht alle bestehenden Chunks einer Datei aus der Supabase-Datenbank."""
    if not SUPABASE_CONNECTION_STRING:
        return False
    try:
        conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM documents 
            WHERE metadata->>'file_name' = %s;
        """, (file_name,))
        deleted_rows = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        print(f"Bereinigung: {deleted_rows} alte(r) Chunk(s) für '{file_name}' gelöscht.")
        return True
    except Exception as e:
        print(f"Fehler bei der Bereinigung von '{file_name}': {e}")
        return False

def run_mistral_ocr_pages(file_path):
    """Konvertiert PDF via Mistral OCR REST API in eine Liste von Seiten-Markdowns."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY fehlt in der .env-Datei!")
        
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}"}
    print(f"Lade {file_path} zu Mistral AI hoch...")
    
    # 1. Datei hochladen
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "application/pdf")}
        data = {"purpose": "ocr"}
        response = requests.post(
            "https://api.mistral.ai/v1/files",
            headers=headers,
            files=files,
            data=data
        )
        
    if response.status_code != 200:
        raise Exception(f"Fehler beim Upload: {response.text}")
        
    file_id = response.json()["id"]
    print(f"Datei erfolgreich hochgeladen. File-ID: {file_id}. Starte OCR-Verarbeitung...")
    
    # 2. OCR-Prozess starten
    ocr_payload = {
        "model": "mistral-ocr-latest",
        "document": {"file_id": file_id}
    }
    ocr_response = requests.post(
        "https://api.mistral.ai/v1/ocr",
        headers=headers,
        json=ocr_payload
    )
    
    if ocr_response.status_code != 200:
        raise Exception(f"Fehler bei OCR: {ocr_response.text}")
        
    ocr_data = ocr_response.json()
    
    pages = ocr_data.get("pages", [])
    # Eine Liste von Markdown-Inhalten pro Seite zurückgeben
    return [page.get("markdown", "") for page in pages]

def chunk_text(text, chunk_size=1000):
    """
    Zerschneidet den Text logisch nach Absätzen (Paragraphs).
    Sammelt Absätze, bis die Zielgröße (chunk_size = 1000) überschritten wird.
    Wenn ein Absatz alleine die Zielgröße überschreitet, wird er satzweise aufgeteilt,
    wobei der Split exakt am ersten Punkt (.), Ausrufezeichen (!) oder Fragezeichen (?)
    erfolgt, der nach Erreichen von 1000 Zeichen auftritt (nicht bei Kommas).
    Erkennt spezielle [PAGE_NUM: X] Tags und ordnet sie den Chunks zu.
    """
    import re
    # Spaltet den Text in Absätze (geteilt durch doppelte oder mehrfache Zeilenumbrüche)
    raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    chunks_with_metadata = []
    current_chunk = []
    current_len = 0
    current_page = None
    
    for p in raw_paragraphs:
        # Prüfen, ob ein Seitenmarker im Absatz liegt
        page_match = re.search(r'\[PAGE_NUM:\s*(\d+)\]', p)
        if page_match:
            current_page = int(page_match.group(1))
            p = re.sub(r'\[PAGE_NUM:\s*\d+\]', '', p).strip()
            if not p:
                continue
        
        p_len = len(p)
        
        # Falls dieser Absatz allein die 1000 Zeichen überschreitet:
        if p_len > chunk_size:
            # Speichere zuerst den bisherigen Chunk
            if current_chunk:
                chunks_with_metadata.append({
                    "content": "\n\n".join(current_chunk),
                    "page_number": current_page
                })
                current_chunk = []
                current_len = 0
            
            # Zerlege den Riesen-Absatz satzweise.
            # Wir splitten bei . oder ! oder ? gefolgt von Leerzeichen.
            sentences = re.split(r'(?<=[.!?])\s+', p)
            
            temp_chunk = []
            temp_len = 0
            for s in sentences:
                s_len = len(s)
                # Füge den Satz hinzu
                temp_chunk.append(s)
                temp_len += s_len + 1 # +1 für Leerzeichen
                
                # Wenn wir die Grenze von 1000 Zeichen überschritten haben:
                if temp_len >= chunk_size:
                    chunks_with_metadata.append({
                        "content": " ".join(temp_chunk).strip(),
                        "page_number": current_page
                    })
                    temp_chunk = []
                    temp_len = 0
                    
            if temp_chunk:
                chunks_with_metadata.append({
                    "content": " ".join(temp_chunk).strip(),
                    "page_number": current_page
                })
                
        else:
            # Normaler Absatz: Passt er noch in die 1000 Zeichen des aktuellen Chunks?
            if current_len + p_len > chunk_size and current_chunk:
                # Alten Chunk speichern
                chunks_with_metadata.append({
                    "content": "\n\n".join(current_chunk),
                    "page_number": current_page
                })
                current_chunk = [p]
                current_len = p_len
            else:
                current_chunk.append(p)
                current_len += p_len + 2 # +2 für \n\n
                
    # Letzten Chunk speichern
    if current_chunk:
        chunks_with_metadata.append({
            "content": "\n\n".join(current_chunk),
            "page_number": current_page
        })
        
    return chunks_with_metadata

def generate_embedding(text):
    """Erzeugt ein 1024-D Embedding via Mistral mistral-embed."""
    return generate_embeddings_batch([text])[0]

def generate_embeddings_batch(texts):
    """Erzeugt Embeddings für eine Liste von Texten via Mistral in Batch-Aufrufen mit Rate-Limit-Schutz."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY fehlt in der .env-Datei!")
        
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-embed",
        "input": []
    }
    
    batch_size = 16
    all_embeddings = []
    import time
    
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        payload["input"] = batch_texts
        
        # Sende Request mit Retry-Logik bei Rate-Limits (HTTP 429)
        retries = 5
        wait_time = 2.0
        while retries > 0:
            try:
                response = requests.post(
                    "https://api.mistral.ai/v1/embeddings",
                    headers=headers,
                    json=payload
                )
                if response.status_code == 200:
                    break
                elif response.status_code == 429:
                    print(f"Rate Limit (429) bei Mistral erreicht. Warte {wait_time}s... (Versuche übrig: {retries})")
                    time.sleep(wait_time)
                    wait_time *= 1.5  # Exponentieller Backoff
                    retries -= 1
                else:
                    raise Exception(f"API Fehler {response.status_code}: {response.text}")
            except Exception as e:
                if retries == 1:
                    raise e
                time.sleep(wait_time)
                retries -= 1
                
        if response.status_code != 200:
            raise Exception(f"Fehler bei Mistral Embeddings nach Retries: {response.text}")
            
        data = response.json()["data"]
        # Nach dem ursprünglichen Index sortieren, um die Reihenfolge beizubehalten
        sorted_data = sorted(data, key=lambda x: x["index"])
        for item in sorted_data:
            all_embeddings.append(item["embedding"])
            
        # Kurze Pause zwischen den Batches, um Rate-Limits zu schonen
        time.sleep(0.2)
        
    return all_embeddings

def get_pcloud_link(file_name):
    """Fragt über die pCloud-API den Freigabelink für eine Datei im Ordner /RAG_Documents/ ab."""
    if not PCLOUD_USERNAME or not PCLOUD_PASSWORD:
        return None
        
    try:
        # 1. Login
        login_url = f"https://api.pcloud.com/login?username={PCLOUD_USERNAME}&password={PCLOUD_PASSWORD}"
        res = requests.get(login_url)
        if res.status_code != 200:
            return None
        login_data = res.json()
        if login_data.get("result") != 0:
            print(f"pCloud-Login fehlgeschlagen: {login_data.get('error')}")
            return None
            
        auth_token = login_data.get("auth")
        
        # 2. Öffentlichen Link holen (Pfad /RAG_Documents/[Dateiname])
        path = f"/RAG_Documents/{file_name}"
        pub_url = f"https://api.pcloud.com/getfilepublink?auth={auth_token}&path={path}"
        pub_res = requests.get(pub_url)
        if pub_res.status_code != 200:
            return None
        pub_data = pub_res.json()
        
        if pub_data.get("result") == 0:
            return pub_data.get("link")
        else:
            print(f"Fehler beim Holen des pCloud-Links für {file_name}: {pub_data.get('error')}")
            return None
    except Exception as e:
        print(f"Fehler bei pCloud-API-Verbindung: {e}")
        return None

def save_chunks_to_db(chunks, file_name, file_hash):
    """Speichert die Chunks samt Embeddings und Metadaten in Supabase."""
    save_custom_chunks_to_db(chunks, file_name, file_hash, None, None, None, 0, None, None)

def save_custom_chunks_to_db(chunks, file_name, file_hash, course=None, module=None, url=None, lesson_index=0, original_path=None, page_number=None):
    """Speichert Chunks mit erweitertem Metadaten-Objekt in Supabase."""
    if not SUPABASE_CONNECTION_STRING:
        raise ValueError("SUPABASE_CONNECTION_STRING fehlt in der .env-Datei!")
        
    # Chunks in Textliste umwandeln für Embedding-Berechnung
    text_list = [item.get("content", "") if isinstance(item, dict) else item for item in chunks]
    embeddings = generate_embeddings_batch(text_list)
    
    # pCloud Freigabelink holen falls anwendbar (nur für PDFs/MDs/TXTs)
    pcloud_url = None
    if not course:
        pcloud_url = get_pcloud_link(file_name)
    
    conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
    cur = conn.cursor()
    
    for i, item in enumerate(chunks):
        embedding = embeddings[i]
        
        # Prüfen, ob der Chunk ein Dictionary (mit eigenem page_number) oder ein String ist
        if isinstance(item, dict):
            chunk_content = item.get("content", "")
            chunk_page = item.get("page_number") or page_number
        else:
            chunk_content = item
            chunk_page = page_number

        metadata = {
            "file_name": file_name,
            "file_hash": file_hash,
            "chunk_index": i
        }
        if course:
            metadata["course"] = course
        if module:
            metadata["module"] = module
        if url:
            metadata["url"] = url
            metadata["lesson_index"] = lesson_index
        if pcloud_url:
            metadata["pcloud_url"] = pcloud_url
        if original_path:
            metadata["original_path"] = original_path
        if chunk_page:
            metadata["page_number"] = chunk_page
            
        cur.execute("""
            INSERT INTO documents (content, metadata, embedding)
            VALUES (%s, %s, %s);
        """, (chunk_content, json.dumps(metadata), embedding))
        
    conn.commit()
    cur.close()
    conn.close()

import shutil

def ensure_file_in_pcloud(file_path):
    """Stellt sicher, dass die Datei im pCloud-Ordner P:\\RAG_Documents liegt."""
    os.makedirs(PCLOUD_DOCS_DIR, exist_ok=True)
    file_name = os.path.basename(file_path)
    target_path = os.path.join(PCLOUD_DOCS_DIR, file_name)
    
    # Falls die Datei nicht bereits dort liegt, kopieren
    if os.path.abspath(file_path) != os.path.abspath(target_path):
        print(f"Kopiere {file_name} nach pCloud: {target_path}...")
        shutil.copy2(file_path, target_path)
    return target_path

def ingest_file(file_path, force=False):
    """Führt die komplette Ingestierungskette für eine Datei aus."""
    if not os.path.exists(file_path):
        print(f"Fehler: Datei {file_path} existiert nicht!")
        return False
        
    original_path = os.path.abspath(file_path)
    file_name = os.path.basename(file_path)
    
    # Vor dem Ingestieren stellen wir sicher, dass die Datei auf pCloud liegt!
    try:
        file_path = ensure_file_in_pcloud(file_path)
    except Exception as e:
        print(f"Warnung beim Kopieren nach pCloud: {e}. Fahre mit Originaldatei fort.")
        
    file_hash = get_file_hash(file_path)
    
    print(f"--- Starte Ingestierung für {file_name} ---")
    
    # Überprüfen, ob bereits indiziert
    if not force and check_if_already_ingested(file_hash):
        print(f"Datei '{file_name}' ist bereits indiziert (MD5-Hash stimmt überein). Überspringe.")
        print("-> Tipp: Nutze das --force Flag, um die Datei neu einzulesen und zu chunkeln.")
        return True
        
    # Falls erzwungen, löschen wir zuerst alle alten Chunks dieser Datei
    if force:
        delete_file_from_db(file_name)
        
    try:
        # Falls Markdown oder TXT, direkt einlesen, ansonsten OCR für PDFs
        ext = os.path.splitext(file_name)[1].lower()
        if ext in ['.md', '.txt']:
            print(f"Lese Textdatei direkt ein...")
            with open(file_path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
            # Chunking & Speichern
            chunks = chunk_text(markdown_content)
            save_custom_chunks_to_db(chunks, file_name, file_hash, original_path=original_path)
        elif ext == '.json':
            print(f"Verarbeite JSON-Datei im RAM...")
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            if not isinstance(data, list):
                print("Fehler: JSON muss ein Array von Lektionsobjekten sein!")
                return False
                
            total_chunks = 0
            for idx, item in enumerate(data):
                course = item.get("course", "Unbekannter Kurs")
                module = item.get("module", "Unbekanntes Modul")
                url = item.get("url", "")
                note = item.get("note")
                note = note.strip() if note else ""
                transcript = item.get("transcript")
                transcript = transcript.strip() if transcript else ""
                
                lesson_text = f"""# Lektion: {module}
**Kurs:** {course}
**Quell-URL:** [{url}]({url})

## Notizen
{note if note else "*Keine Notizen*"}

## Transkript
{transcript if transcript else "*Kein Transkript*"}
"""
                lesson_chunks = chunk_text(lesson_text)
                if lesson_chunks:
                    save_custom_chunks_to_db(lesson_chunks, file_name, file_hash, course, module, url, idx)
                    total_chunks += len(lesson_chunks)
            print(f"JSON-Indizierung beendet. {total_chunks} Chunks gespeichert.")
        elif ext == '.pdf':
            pages_md = run_mistral_ocr_pages(file_path)
            print(f"OCR erfolgreich. {len(pages_md)} Seiten extrahiert.")
            
            # Volltext mit Seiten-Markern erstellen (erhält Absatzkontext über Seitengrenzen hinweg)
            full_text = ""
            for idx, page_content in enumerate(pages_md):
                page_number = idx + 1
                full_text += f"\n\n[PAGE_NUM: {page_number}]\n\n" + page_content
                
            chunks = chunk_text(full_text)
            save_custom_chunks_to_db(chunks, file_name, file_hash, original_path=original_path)
            print(f"PDF-Indizierung beendet. {len(chunks)} Chunks gespeichert.")
        else:
            print(f"Fehler: Dateiformat {ext} wird nicht unterstützt!")
            return False
            
        return True
        
    except Exception as e:
        print(f"Fehler bei der Ingestierung von {file_name}: {e}")
        return False

if __name__ == "__main__":
    # Prüfen, ob --force Flag übergeben wurde
    force_flag = "--force" in sys.argv
    files_to_ingest = [arg for arg in sys.argv[1:] if arg != "--force"]
    
    if not files_to_ingest:
        print("Nutzung: python ingest.py [--force] <pfad_zu_datei1> <pfad_zu_datei2> ...")
        sys.exit(1)
        
    success_count = 0
    for file_path in files_to_ingest:
        if ingest_file(file_path, force=force_flag):
            success_count += 1
            
    print(f"\nFertig! {success_count} von {len(files_to_ingest)} Dateien erfolgreich indiziert.")
