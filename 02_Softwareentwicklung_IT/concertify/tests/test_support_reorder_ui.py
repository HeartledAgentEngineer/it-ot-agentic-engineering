"""
tests/test_support_reorder_ui.py
=================================
Regression: Grip-Handle + Drag&Drop-Verdrahtung im grossen Template.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _template_text() -> str:
    return (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_grip_handle_present():
    text = _template_text()
    assert 'class="support-act-grip"' in text
    assert 'ondragstart="supportGripDragStart(event)"' in text


def test_drag_functions_defined():
    text = _template_text()
    assert "function supportGripDragStart(" in text
    assert "function supportListDragOver(" in text
    assert "function supportGripDragEnd(" in text
    assert "function _persistSupportOrder(" in text
    assert "/reorder_support_acts" in text


def test_both_lists_have_dragover_handler():
    text = _template_text()
    # Mindestens zwei dragover-Verdrahtungen (Mix-Tab-Liste + Abend-Liste)
    assert text.count('ondragover="supportListDragOver(event)"') >= 2
