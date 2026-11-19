"""Pruebas de las advertencias de memoria y Java. Sin Java, red ni PySide6."""
from managers.resource_advisor import MANY_MODS, MAX_RAM_CAP, assess, suggested_max_ram


def levels(advice):
    return [item.level for item in advice]


def test_no_warnings_for_a_small_pack_with_enough_ram():
    advice = assess(mod_count=0, jar_mb=0, max_ram_mb=2048, system_total_mb=16384,
                    java_present=True, java_is_64bit=True, java_compatible=True)
    assert advice == []


def test_warns_when_ram_is_too_low_for_the_mods():
    advice = assess(mod_count=40, jar_mb=300, max_ram_mb=2048, system_total_mb=16384,
                    java_present=True, java_is_64bit=True, java_compatible=True)
    assert "aviso" in levels(advice)
    assert str(suggested_max_ram(300)) in advice[0].text


def test_missing_java_is_an_error():
    advice = assess(mod_count=0, jar_mb=0, max_ram_mb=2048, system_total_mb=16384, java_present=False)
    assert levels(advice) == ["error"]


def test_32_bit_java_cannot_use_more_than_one_gigabyte():
    advice = assess(mod_count=0, jar_mb=0, max_ram_mb=4096, system_total_mb=16384,
                    java_present=True, java_is_64bit=False, java_compatible=True)
    assert any("32 bits" in item.text for item in advice)


def test_many_mods_show_slow_start_notice():
    advice = assess(mod_count=MANY_MODS, jar_mb=10, max_ram_mb=8192, system_total_mb=16384,
                    java_present=True, java_is_64bit=True, java_compatible=True)
    assert "info" in levels(advice)


def test_ram_above_three_quarters_of_system_memory_warns():
    advice = assess(mod_count=0, jar_mb=0, max_ram_mb=14000, system_total_mb=16000,
                    java_present=True, java_is_64bit=True, java_compatible=True)
    assert "aviso" in levels(advice)


def test_suggestion_is_capped():
    assert suggested_max_ram(100000) == MAX_RAM_CAP