import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "src" / "skylander_character_editor.py"
spec = importlib.util.spec_from_file_location("skylander_character_editor", MODULE_PATH)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


def test_crc16_ccitt_false_check_value():
    assert app.crc16(b"123456789") == 0x29B1


def test_xp_split_at_level_20():
    assert app.splitxp(199535) == (33000, 63500, 103035)


def test_level_thresholds():
    assert app.level_for(0) == 1
    assert app.level_for(184000) == 19
    assert app.level_for(199535) == 20


def test_sequence_counter_wraparound():
    assert app.newer(0, 255)
    assert not app.newer(255, 0)


def test_initialization_supports_recognized_non_trap_team_character():
    raw = bytearray(1024)
    # Gill Grunt is a standard Skylander from Spyro's Adventure (ID 0x000E).
    raw[0x10:0x12] = (14).to_bytes(2, "little")
    progress = app.initialize_character_plain(raw, 20, 65000)
    assert app.active(progress)[0] is not None
    assert app.active(progress)[1] is not None


def test_initialization_rejects_unknown_id():
    raw = bytearray(1024)
    raw[0x10:0x12] = (999).to_bytes(2, "little")
    try:
        app.initialize_character_plain(raw, 20, 65000)
    except ValueError as exc:
        assert "recognized character figures" in str(exc)
    else:
        raise AssertionError("Unknown ID should not be initialized")
