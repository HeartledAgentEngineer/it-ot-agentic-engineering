# Changelog 01.11.2026 — Buchstaben-Sprungleiste in „Personen benennen“ wirkte nicht

## Befund (Handy)
Reiter „Benannt“, alphabetisch sortiert: Ein Tipp auf einen Buchstaben (z. B. „I“) markierte nur den Knopf,
die Liste blieb bei „A“ stehen.

## Ursache
`sprungZu` in `frontend/gruppen_quiz.js` suchte das Ziel mit
`z.attributes['data-sprung'] === buchstabe`. Im Browser ist `attributes[name]` ein **Attr-Objekt**, kein Text —
der Vergleich war nie wahr, es wurde weder markiert noch gerollt. Die Test-Attrappe
(`frontend/tests/test_gruppen_personenliste.js`) speicherte Attribute als Text, deshalb war der Test grün.

## Reparatur
- `sprungZu` liest das Ziel über `getAttribute('data-sprung')`.
- Attrappe browsergleich: `attributes[name]` ist ein Objekt `{name, value}`, dazu `getAttribute`;
  drei Testzeilen nutzen `getAttribute`.
- Cache-Bump `gruppen_quiz.js?v=20261101G`.

## Beleg
- Mit browsergleicher Attrappe und altem Code: `sprungmarkenNurVorhandeneUndZumZiel` rot.
- Nach der Reparatur: `node frontend/tests/test_gruppen_personenliste.js` grün;
  `pytest tests/test_frontend_node.py` 59 passed.

## Hinweis
Die Leiste **springt** zum ersten Namen des Buchstabens (so seit S8, 18.10.2026), sie filtert nicht.
