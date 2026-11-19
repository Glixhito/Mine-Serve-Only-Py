"""Pruebas del seguimiento de jugadores y de las listas guardadas. No requieren Java ni PySide6."""
from core.event_manager import EventManager
from managers.player_tracker import PlayerTracker, read_name_list


def test_join_and_leave_update_online_players():
    events = EventManager()
    tracker = PlayerTracker(events)
    events.publish("server.log", server_id=1, line="[12:00:00] [Server thread/INFO]: Steve joined the game")
    events.publish("server.log", server_id=1, line="[12:01:00] [Server thread/INFO]: Alex joined the game")
    events.publish("server.log", server_id=1, line="[12:02:00] [Server thread/INFO]: Steve left the game")
    assert tracker.online(1) == ["Alex"]


def test_list_response_sets_players_and_limit():
    events = EventManager()
    tracker = PlayerTracker(events)
    events.publish("server.log", server_id=1,
                   line="[12:05:00] [Server thread/INFO]: There are 2 of a max of 20 players online: Steve, Alex")
    assert tracker.online(1) == ["Alex", "Steve"]
    assert tracker.max_players(1) == 20


def test_stopping_the_server_clears_players():
    events = EventManager()
    tracker = PlayerTracker(events)
    events.publish("server.log", server_id=1, line="[12:00:00] [Server thread/INFO]: Steve joined the game")
    events.publish("server.status_changed", server_id=1, status="detenido")
    assert tracker.online(1) == []


def test_reads_whitelist_names(tmp_path):
    (tmp_path / "whitelist.json").write_text('[{"uuid": "x", "name": "Steve"}]', encoding="utf-8")
    assert read_name_list(tmp_path, "whitelist.json") == ["Steve"]


def test_missing_or_broken_file_returns_empty(tmp_path):
    assert read_name_list(tmp_path, "ops.json") == []
    (tmp_path / "banned-players.json").write_text("no es json", encoding="utf-8")
    assert read_name_list(tmp_path, "banned-players.json") == []