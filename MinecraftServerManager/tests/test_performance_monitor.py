"""Rendimiento en juego: tirones del log, jugadores conectados y consejos. Reloj simulado, sin red."""
from core.event_manager import EventManager
from managers.performance_monitor import PerformanceMonitor, advice, WINDOW_S, LagSummary


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _publish(events: EventManager, line: str, server_id: int = 1) -> None:
    events.publish("server.log", server_id=server_id, line=line)


def test_lag_warning_is_counted_with_its_delay():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[12:00:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? "
                     "Running 2371ms or 47 ticks behind")
    summary = monitor.summary(1)
    assert summary.count == 1 and summary.worst_ms == 2371


def test_older_lag_format_is_also_read():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[00:00:08] [Server thread/WARN]: Can't keep up! Did the system time change, or is the "
                     "server overloaded? Running 3284ms behind, skipping 65 tick(s)")
    assert monitor.summary(1).worst_ms == 3284


def test_lag_older_than_ten_minutes_is_not_counted():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[12:00:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2000ms or 40 ticks behind")
    clock.now = WINDOW_S + 1
    assert monitor.summary(1).count == 0


def test_players_are_tracked_and_cleared_on_stop():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[13:00:00] [Server thread/INFO]: Cristian joined the game")
    _publish(events, "[13:00:05] [Server thread/INFO]: System chat: Ana joined the game")
    _publish(events, "[13:01:00] [Server thread/INFO]: Cristian left the game")
    assert monitor.summary(1).players == 1
    _publish(events, "[13:02:00] [Server thread/INFO]: Stopping the server")
    assert monitor.summary(1).players == 0


def test_chat_text_does_not_count_as_a_player():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[13:00:00] [Server thread/INFO]: <Pepe> Cristian joined the game")
    assert monitor.summary(1).players == 0


def test_servers_are_counted_separately():
    events, clock = EventManager(), FakeClock()
    monitor = PerformanceMonitor(events, clock=clock)
    _publish(events, "[12:00:00] [Server thread/WARN]: Can't keep up! Is the server overloaded? Running 2000ms or 40 ticks behind", server_id=2)
    assert monitor.summary(1).count == 0 and monitor.summary(2).count == 1


def test_advice_without_lag_says_so():
    assert advice(LagSummary(0, 0, 3), ram_mb=1000, max_ram_mb=4096) == ["Sin tirones en los últimos 10 minutos."]


def test_advice_points_to_memory_when_ram_is_almost_full():
    lines = advice(LagSummary(4, 3000, 2), ram_mb=3900, max_ram_mb=4096)
    assert "Sube la RAM" in lines[1]


def test_advice_points_to_mods_when_memory_has_margin():
    lines = advice(LagSummary(4, 3000, 2), ram_mb=1200, max_ram_mb=4096)
    assert "mods" in lines[1]