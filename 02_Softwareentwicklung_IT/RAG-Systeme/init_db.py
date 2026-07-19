# ==============================================================================
# Script      : init_db.py
# Author      : Sebastian
# Date        : 2026-07-11
# Version     : 1.0
# Description : Initialisiert die Supabase-Datenbank (pgvector, Tabelle documents,
#               Suchindex und die SQL-Funktion hybrid_search für RRF).
# ==============================================================================

import os
import sys
import psycopg2
from dotenv import load_dotenv

# .env-Datei laden
load_dotenv()

def init_db():
    conn_string = os.getenv("SUPABASE_CONNECTION_STRING")
    if not conn_string:
        print("Fehler: SUPABASE_CONNECTION_STRING ist nicht in der .env-Datei oder Umgebung definiert!")
        print("Bitte füge SUPABASE_CONNECTION_STRING=postgresql://user:pass@db.supabase.co:5432/postgres hinzu.")
        sys.exit(1)
        
    print("Verbindung zu Supabase wird aufgebaut...")
    try:
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 1. pgvector Extension aktivieren
        print("Aktiviere pgvector-Erweiterung...")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Tabelle zurücksetzen, um Dimensionen auf 1024 ändern zu können
        print("Setze alte documents-Tabelle zurück (falls vorhanden)...")
        cur.execute("DROP TABLE IF EXISTS documents CASCADE;")
        
        # 2. Tabelle documents erstellen (mit 1024 Dimensionen für Mistral Embeddings)
        print("Erstelle Tabelle 'documents' mit 1024 Dimensionen...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                content TEXT NOT NULL,
                metadata JSONB,
                embedding vector(1024)
            );
        """)
        
        # 3. HNSW-Index für Vektorsuche anlegen
        print("Erstelle HNSW-Index für Vektoren...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_embedding_idx 
            ON documents USING hnsw (embedding vector_cosine_ops);
        """)
        
        # 4. GIN-Index für Volltextsuche anlegen
        print("Erstelle GIN-Index für Volltextsuche...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS documents_fts_idx 
            ON documents USING gin(to_tsvector('german', content));
        """)
        
        # 5. SQL-Suchfunktion hybrid_search anlegen
        print("Erstelle SQL-Funktion 'hybrid_search'...")
        cur.execute("""
            CREATE OR REPLACE FUNCTION hybrid_search(
                query_text TEXT,
                query_embedding vector(1024),
                match_count INT,
                rrf_k INT DEFAULT 60
            )
            RETURNS TABLE (
                id UUID,
                content TEXT,
                metadata JSONB,
                similarity FLOAT,
                rrf_score FLOAT
            )
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RETURN QUERY
                WITH vector_matches AS (
                    SELECT
                        d.id,
                        1 - (d.embedding <=> query_embedding) AS similarity,
                        ROW_NUMBER() OVER (ORDER BY d.embedding <=> query_embedding) AS rank
                    FROM documents d
                    ORDER BY d.embedding <=> query_embedding
                    LIMIT match_count * 2
                ),
                fts_matches AS (
                    SELECT
                        d.id,
                        ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('german', d.content), plainto_tsquery('german', query_text)) DESC) AS rank
                    FROM documents d
                    WHERE to_tsvector('german', d.content) @@ plainto_tsquery('german', query_text)
                    ORDER BY ts_rank_cd(to_tsvector('german', d.content), plainto_tsquery('german', query_text)) DESC
                    LIMIT match_count * 2
                )
                SELECT
                    d.id,
                    d.content,
                    d.metadata,
                    COALESCE(v.similarity, 0.0)::FLOAT AS similarity,
                    (
                        COALESCE(1.0 / (rrf_k + v.rank), 0.0) +
                        COALESCE(1.0 / (rrf_k + f.rank), 0.0)
                    )::FLOAT AS rrf_score
                FROM documents d
                LEFT JOIN vector_matches v ON d.id = v.id
                LEFT JOIN fts_matches f ON d.id = f.id
                WHERE v.id IS NOT NULL OR f.id IS NOT NULL
                ORDER BY rrf_score DESC
                LIMIT match_count;
            END;
            $$;
        """)
        
        cur.close()
        conn.close()
        print("Datenbank erfolgreich initialisiert!")
        
    except Exception as e:
        print(f"Fehler bei der Datenbank-Initialisierung: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
