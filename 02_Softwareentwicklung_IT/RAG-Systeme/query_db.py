# ==============================================================================
# Script      : query_db.py
# Author      : Sebastian
# Date        : 2026-07-11
# Version     : 1.0
# Description : CLI-Tool zur Abfrage der RAG-Pipeline (Hybrid-Search + Gemini LLM).
# ==============================================================================

import os
import sys
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

# Lokales Modell konfigurieren (z. B. via Ollama)
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "False").lower() == "true"
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:11434/api/chat")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.1")

# Gemini API für Textgenerierung konfigurieren
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

def generate_query_embedding(query_text):
    """Erzeugt ein 1024-D Embedding für die Frage via Mistral mistral-embed."""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY fehlt in der .env-Datei!")
        
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-embed",
        "input": [query_text]
    }
    response = requests.post(
        "https://api.mistral.ai/v1/embeddings",
        headers=headers,
        json=payload
    )
    if response.status_code != 200:
        raise Exception(f"Fehler bei Mistral Embeddings: {response.text}")
        
    return response.json()["data"][0]["embedding"]

def search_db(query_text, match_count=5):
    """Führt die Hybrid-Suche in Supabase durch."""
    if not SUPABASE_CONNECTION_STRING:
        raise ValueError("SUPABASE_CONNECTION_STRING fehlt in der .env-Datei!")
        
    query_embedding = generate_query_embedding(query_text)
    
    conn = psycopg2.connect(SUPABASE_CONNECTION_STRING)
    cur = conn.cursor()
    
    # hybrid_search-Funktion in Postgres aufrufen
    cur.execute("""
        SELECT content, metadata, similarity, rrf_score 
        FROM hybrid_search(%s, %s::vector, %s);
    """, (query_text, query_embedding, match_count))
    
    results = cur.fetchall()
    cur.close()
    conn.close()
    
    chunks = []
    for row in results:
        chunks.append({
            "content": row[0],
            "metadata": row[1],
            "similarity": row[2],
            "rrf_score": row[3]
        })
    return chunks

def generate_answer(query_text, context_chunks):
    """Generiert die Antwort basierend auf den Chunks (mit lokalem LLM oder Gemini als Fallback)."""
    # Kontext formatieren
    formatted_context = ""
    for i, chunk in enumerate(context_chunks):
        meta = chunk["metadata"]
        if "course" in meta and "module" in meta:
            source = f"{meta['course']} -> {meta['module']}"
        else:
            source = meta.get("file_name", "Unbekannt")
        formatted_context += f"--- DOKUMENT {i+1} (Quelle: {source}) ---\n{chunk['content']}\n\n"
        
    prompt = f"""
Du bist ein hilfreicher und präziser KI-Assistent.
Beantworte die folgende Frage sachlich und präzise auf Deutsch, basierend AUSSCHLIESSLICH auf den bereitgestellten Kontext-Dokumenten.

Nutze in deiner Antwort zwingend nummerierte inline-Zitate (z.B. [1] oder [2]), die sich auf die jeweiligen Quellen (z.B. "DOKUMENT 1", "DOKUMENT 2" etc.) im bereitgestellten Kontext beziehen. Beispiel: "Gemäß der Anleitung [1] müssen..." oder "Das Setup besteht aus folgenden Teilen [3]". Platziere diese Zitate direkt hinter den entsprechenden Aussagen.

Falls die Antwort nicht im Kontext enthalten ist, antworte ehrlich mit: "Ich konnte keine passenden Informationen in den Dokumenten finden."
Erfinde keine Fakten. Nenne am Ende KEINE separate Quellenliste als Text, da die Quellen über die Zitate und das UI übersichtlich zugeordnet werden.

Kontext:
{formatted_context}

Frage:
{query_text}

ANTWORT:
"""

    if USE_LOCAL_LLM:
        try:
            payload = {
                "model": LOCAL_LLM_MODEL,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            response = requests.post(LOCAL_LLM_URL, json=payload, timeout=30)
            if response.status_code == 200:
                return response.json()["message"]["content"]
            else:
                raise Exception(f"Lokaler LLM-Fehler (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"Warnung: Lokales LLM (Ollama) fehlgeschlagen: {e}. Versuche Gemini...")

    # 2. Standard: Gemini API
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Warnung: Gemini API fehlgeschlagen (z. B. Kontingent erschöpft): {e}. Versuche Mistral...")

    # 3. Fallback: Mistral API (nutzt den in der .env hinterlegten MISTRAL_API_KEY)
    if MISTRAL_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "open-mixtral-8x22b",  # Alternatives schnelles Mistral-Modell
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            }
            res = requests.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                return res.json()["choices"][0]["message"]["content"]
            else:
                raise Exception(f"Mistral API Status {res.status_code}: {res.text}")
        except Exception as e:
            print(f"Warnung: Mistral API ebenfalls fehlgeschlagen: {e}")

    raise ValueError("Kein aktives LLM-Modell konnte erfolgreich aufgerufen werden (alle Fallbacks fehlgeschlagen).")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Nutzung: python query_db.py \"Deine Frage hier\"")
        sys.exit(1)
        
    query = sys.argv[1]
    print(f"Frage: {query}\nSearching database...")
    
    try:
        # Suche in DB
        chunks = search_db(query, match_count=5)
        
        if not chunks:
            print("Keine relevanten Dokumente in der Datenbank gefunden.")
            sys.exit(0)
            
        print(f"{len(chunks)} relevante Abschnitte gefunden. Generiere Antwort...")
        
        # Antwort erzeugen
        answer = generate_answer(query, chunks)
        
        print("\n=== ANTWORT ===")
        print(answer)
        print("================")
        
    except Exception as e:
        print(f"Fehler bei der Abfrage: {e}")
        sys.exit(1)
