"""Absatz-Chunking fuer die Ingestion: reine Logik ohne API- oder DB-Zugriff, daher offline testbar."""
import re


def chunk_text(text, chunk_size=1000):
    """
    Zerschneidet den Text logisch nach Absätzen (Paragraphs).
    Sammelt Absätze, bis die Zielgröße (chunk_size = 1000) überschritten wird.
    Wenn ein Absatz alleine die Zielgröße überschreitet, wird er satzweise aufgeteilt,
    wobei der Split exakt am ersten Punkt (.), Ausrufezeichen (!) oder Fragezeichen (?)
    erfolgt, der nach Erreichen von 1000 Zeichen auftritt (nicht bei Kommas).
    Erkennt spezielle [PAGE_NUM: X] Tags und ordnet sie den Chunks zu.
    """
    # Spaltet den Text in Absätze (geteilt durch doppelte oder mehrfache Zeilenumbrüche)
    raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    chunks_with_metadata = []
    current_chunk = []
    current_len = 0
    current_page = None
    chunk_page = None
    
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
                    "page_number": chunk_page
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
                    "page_number": chunk_page
                })
                current_chunk = [p]
                chunk_page = current_page
                current_len = p_len
            else:
                if not current_chunk:
                    chunk_page = current_page  # Seite, auf der der Chunk beginnt
                current_chunk.append(p)
                current_len += p_len + 2 # +2 für \n\n
                
    # Letzten Chunk speichern
    if current_chunk:
        chunks_with_metadata.append({
            "content": "\n\n".join(current_chunk),
            "page_number": chunk_page
        })
        
    return chunks_with_metadata
