"""Pruebas del lado de cada mod (cliente, servidor o ambos). Sin red ni PySide6."""
from managers.mod_sides import blocks_server, side_label


def test_client_only_mod_is_blocked_on_server():
    assert side_label("required", "unsupported") == "Cliente"
    assert blocks_server("unsupported") is True


def test_server_only_mod():
    assert side_label("unsupported", "required") == "Servidor"


def test_both_sides_are_allowed_on_server():
    assert side_label("required", "required") == "Ambos"
    assert side_label("optional", "required") == "Ambos"
    assert blocks_server("required") is False


def test_unknown_when_there_is_no_data():
    assert side_label(None, None) == "Desconocido"
    assert side_label("unknown", "unknown") == "Desconocido"