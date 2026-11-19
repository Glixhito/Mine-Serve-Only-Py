"""Rutas de recursos: funcionan en el proyecto y dentro del instalador (sys._MEIPASS)."""
import sys
from pathlib import Path

import utils
from utils.resources import resource_path


def test_resource_points_to_project_when_not_frozen():
    project = Path(utils.__file__).resolve().parent.parent
    assert resource_path("assets/icono.ico") == project / "assets" / "icono.ico"


def test_resource_points_into_meipass_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resource_path("assets/icono.ico") == tmp_path / "assets" / "icono.ico"