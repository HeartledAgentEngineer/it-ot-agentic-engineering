"""Version und Commit dieser typeFREE-Fassung.

Im Quellcode steht immer `dev`/`lokal`. Jeder Build (`typeFREE.spec`) schreibt vorher
`_version_build.py` frisch (nicht versioniert, siehe `ci/version_schreiben.py`), und nur die
EXE (`sys.frozen`) liest es — eine liegengebliebene Datei ändert den Quellcodestart nicht.
Die EXE trägt so Version und Commit, und die Startzeile im Log zeigt, welche Fassung wirklich läuft. Anlass: Im August
2026 lief wochenlang ein veralteter Build, ohne dass es jemand sehen konnte.
"""
import sys

VERSION = 'dev'
COMMIT = 'lokal'

if getattr(sys, 'frozen', False):           # nur in der gebauten EXE
    try:
        from _version_build import VERSION, COMMIT  # noqa: F401  (vom Build erzeugt)
    except ImportError:
        pass
