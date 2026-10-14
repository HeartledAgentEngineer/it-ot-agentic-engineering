"""Schreibt `windows/_version_build.py` vor dem PyInstaller-Build.

`typeFREE.spec` ruft `schreiben()` bei jedem Build selbst auf (Version aus der Umgebungs-
variable TYPEFREE_VERSION, sonst `dev`; Commit aus TYPEFREE_COMMIT oder git). Von Hand nur
zum Ausprobieren — Aufruf (aus dem Projektordner typeFREE):
    py -3.12 ci/version_schreiben.py                     # Version 'dev', Commit aus git
    py -3.12 ci/version_schreiben.py --version typefree-v1.2.0 --commit 85b072b

Der Tag-Vorsatz `typefree-v` wird abgeschnitten. Version und Commit werden geprüft und
mit repr() geschrieben — aus einem Tag-Namen wird nie ausführbarer Code.
"""
import argparse
import pathlib
import re
import subprocess

ZIEL = pathlib.Path(__file__).resolve().parents[1] / 'windows' / '_version_build.py'
VERSION_MUSTER = re.compile(r'^(dev|\d+\.\d+\.\d+)$')
COMMIT_MUSTER = re.compile(r'^[0-9a-f]{7,40}$')


def version_bereinigen(roh):
    """`typefree-v1.2.0` → `1.2.0`; wirft ValueError bei allem anderen als X.Y.Z oder dev."""
    version = roh.removeprefix('typefree-v').removeprefix('v')
    if not VERSION_MUSTER.match(version):
        raise ValueError(f'ungültige Version: {roh!r} (erwartet X.Y.Z oder typefree-vX.Y.Z)')
    return version


def commit_pruefen(commit):
    commit = commit.strip().lower()
    if not COMMIT_MUSTER.match(commit):
        raise ValueError(f'ungültiger Commit: {commit!r}')
    return commit[:7]


def git_commit():
    return subprocess.run(['git', 'rev-parse', '--short=7', 'HEAD'], capture_output=True,
                          text=True, check=True).stdout


def inhalt(version, commit):
    return ('# Vom Build erzeugt (ci/version_schreiben.py) — nicht versionieren.\n'
            f'VERSION = {version!r}\nCOMMIT = {commit!r}\n')


def schreiben(version, commit, ziel=ZIEL):
    ziel.write_text(inhalt(version_bereinigen(version), commit_pruefen(commit)),
                    encoding='utf-8')
    return ziel


def main():
    zerleger = argparse.ArgumentParser(description=__doc__,
                                       formatter_class=argparse.RawDescriptionHelpFormatter)
    zerleger.add_argument('--version', default='dev')
    zerleger.add_argument('--commit', default=None)
    argumente = zerleger.parse_args()
    ziel = schreiben(argumente.version, argumente.commit or git_commit())
    print(f'{ziel.name}: {ziel.read_text(encoding="utf-8").splitlines()[1:]}')


if __name__ == '__main__':
    main()
