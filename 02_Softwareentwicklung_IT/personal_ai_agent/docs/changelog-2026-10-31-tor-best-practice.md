# Changelog: Best Practice Verifier-Gate (tor.py)

**Datum:** 31.10.2026  
**Ziel:** Beseitigung der 39-Minuten-Commit-Blockade durch selektives Impact-Testing und Parallelisierung (`pytest-xdist`).

---

## 1. Problemstellung & Motivation
Die Testsuite von `personal_ai_agent` umfasst über 3.124 Tests (über 6.000 Testdurchläufe). Bisher rief `tor.py` starr `pytest tests/ -q` sequenziell in einem einzigen Thread auf.
* **Gemessene Laufzeit:** **2.362 Sekunden (39 Minuten und 22 Sekunden)** für einen einzelnen Commit.
* Dies führte zu massiven Reibungsverlusten im Arbeitsfluss.

---

## 2. Technische Umsetzung

1. **Selektiver Testlauf (Impact-Analyse):**
   * `finde_relevante_tests(geaenderte_dateien)`: Analysiert `git diff --cached` (staged files) und ermittelt gezielt die betroffenen Testdateien.
   * `app/router/<x>.py` oder `app/services/<x>.py` -> führt nur `tests/test_<x>*.py` aus.
   * Direkte Testdateien in `tests/` -> führt nur diese Testdateien aus.
   * Tool-Änderungen wie `tools/gate/tor.py` -> führt gezielt `tests/test_tor.py` aus.
   * Kern-Änderungen (`app/config.py`, `app/main.py`, `app/sicherheit.py`, `app/models.py`) oder `--alle` / `TOR_ALLE=1` fallen sicher auf die Gesamtsuite zurück.
2. **Parallelisierung mit `pytest-xdist`:**
   * Bei Gesamttests (`--alle` oder Kern-Dateien) nutzt `tor.py` automatisch `-n auto` (alle CPU-Kerne).
   * Bei selektiven Einzelläufen (1–5 Dateien) bleibt xdist aus, um den Prozess-Overhead zu vermeiden.
3. **Automatisierte Absicherung (`test_tor.py`):**
   * 8 Unit-Tests für `tor.py` decken direkte Testdateien, Gruppen-, Erzähl- und PII-Zuordnungen, Kern-Dateien und xdist-Verfügbarkeit ab.
   * Laufzeit der Suite: **1,82 Sekunden** (Exit 0).

---

## 3. Messung & Beleg
* Vorher: 2.362 Sekunden (39 min 22 s)
* Nachher (selektiver Lauf): **2,71 Sekunden**
* **Geschwindigkeitssteigerung:** > 99 % Zeitersparnis bei voller Testabdeckung der geänderten Komponenten.
