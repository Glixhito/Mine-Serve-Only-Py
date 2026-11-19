"""Pruebas de las listas de versiones de cargador (funciones puras, sin red)."""
from managers.loader_catalog import fabric_from_entries, forge_from_promos, neoforge_from_metadata, neoforge_prefix

PROMOS = {"1.20.1-recommended": "47.2.0", "1.20.1-latest": "47.3.0", "1.21-latest": "51.0.1"}
XML = """<metadata><versioning><versions>
<version>20.4.1</version><version>20.4.237</version><version>21.0.1</version><version>26.3.5</version>
</versions></versioning></metadata>"""


def test_forge_lists_recommended_first_without_duplicates():
    assert forge_from_promos(PROMOS, "1.20.1") == ["47.2.0", "47.3.0"]
    assert forge_from_promos({"1.20.1-latest": "47.2.0", "1.20.1-recommended": "47.2.0"}, "1.20.1") == ["47.2.0"]
    assert forge_from_promos(PROMOS, "26.3") == []


def test_neoforge_matches_minecraft_and_lists_newest_first():
    assert neoforge_from_metadata(XML, "1.20.4") == ["20.4.237", "20.4.1"]
    assert neoforge_from_metadata(XML, "26.3") == ["26.3.5"]
    assert neoforge_from_metadata(XML, "1.20.1") == []


def test_neoforge_prefix_for_minecraft_formats():
    assert neoforge_prefix("1.21.1") == "21.1."
    assert neoforge_prefix("26.3") == "26.3."


def test_fabric_stable_versions_come_first():
    items = [{"loader": {"version": "0.16.0", "stable": False}},
             {"loader": {"version": "0.16.1", "stable": True}}]
    assert fabric_from_entries(items) == ["0.16.1", "0.16.0"]
    