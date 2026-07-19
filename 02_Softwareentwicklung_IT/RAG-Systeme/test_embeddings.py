# ==============================================================================
# Script      : test_embeddings.py
# Description : Demo-Workflow zum Vergleich von Embeddings (Hund, Katze, Auto)
#               via Mistral-Embed API und Kosinus-Aehnlichkeit.
# ==============================================================================

import os
import math
import requests
from dotenv import load_dotenv

# .env laden
load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    print("Fehler: MISTRAL_API_KEY fehlt in der .env-Datei!")
    exit(1)

def get_embedding(text):
    """Holt das 1024-dimensionale Vektor-Embedding fuer einen Text."""
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-embed",
        "input": [text]
    }
    res = requests.post("https://api.mistral.ai/v1/embeddings", headers=headers, json=payload)
    if res.status_code != 200:
        raise Exception(f"Fehler bei Mistral API ({res.status_code}): {res.text}")
    return res.json()["data"][0]["embedding"]

def cosine_similarity(v1, v2):
    """Berechnet die Kosinus-Aehnlichkeit zwischen zwei Vektoren."""
    dot_product = sum(a*b for a, b in zip(v1, v2))
    magnitude_v1 = math.sqrt(sum(a*a for a in v1))
    magnitude_v2 = math.sqrt(sum(b*b for b in v2))
    if magnitude_v1 == 0 or magnitude_v2 == 0:
        return 0.0
    return dot_product / (magnitude_v1 * magnitude_v2)

def main():
    print("--- Mistral Embedding Testskript ---")
    try:
        print("Lade Embeddings von der Mistral API...")
        emb_hund = get_embedding("Hund")
        emb_katze = get_embedding("Katze")
        emb_auto = get_embedding("Auto")

        print(f"\n1. Vektor-Dimension fuer 'Hund': {len(emb_hund)}")
        print(f"   Auszug der ersten 5 Werte: {emb_hund[:5]}")

        # Kosinus-Aehnlichkeit berechnen
        sim_hund_katze = cosine_similarity(emb_hund, emb_katze)
        sim_hund_auto = cosine_similarity(emb_hund, emb_auto)

        print(f"\n2. Kosinus-Aehnlichkeitsvergleich:")
        print(f"   - Aehnlichkeit ('Hund', 'Katze') : {sim_hund_katze:.4f}")
        print(f"   - Aehnlichkeit ('Hund', 'Auto')  : {sim_hund_auto:.4f}")

        if sim_hund_katze > sim_hund_auto:
            print("\n[OK] BEWEIS ERBRACHT: 'Hund' und 'Katze' sind sich semantisch naeher als 'Hund' und 'Auto'!")
        else:
            print("\n[FEHLER] Fehler: Semantische Anordnung entspricht nicht den Erwartungen.")
            
    except Exception as e:
        print(f"Fehler bei der Ausfuehrung: {e}")

if __name__ == "__main__":
    main()
