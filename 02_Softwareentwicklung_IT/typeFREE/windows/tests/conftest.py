"""Legt den Ordner `windows/` in den Suchpfad, damit `import typefree` klappt."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
