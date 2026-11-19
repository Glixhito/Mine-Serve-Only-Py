"""Mensaje de bienvenida: se envía solo al entrar un jugador, con el servidor activo. Sin red."""
import json

from core.event_manager import EventManager
from managers.welcome_messenger import WelcomeMessenger


class FakeController:
    def __init__(self, running: bool = True) -> None:
        self.running = running
        self.sent: list[str] = []

    def is_running(self, server_id: int) -> bool:
        return self.running

    def send_command(self, server_id: int, command: str) -> None:
        self.sent.append(command)


def _publish(events: EventManager, line: str) -> None:
    events.publish("server.log", server_id=1, line=line)


def test_join_sends_private_greeting_lines():
    events, controller = EventManager(), FakeController()
    WelcomeMessenger(events, controller, lines=("Hola {player}", "Bienvenido"), title=None)
    _publish(events, "[13:29:10] [Server thread/INFO]: Cristian joined the game")
    assert len(controller.sent) == 2
    assert controller.sent[0].startswith("tellraw Cristian ")
    assert json.loads(controller.sent[0].split(" ", 2)[2])["text"] == "Hola Cristian"


def test_accents_are_kept_in_the_message():
    events, controller = EventManager(), FakeController()
    WelcomeMessenger(events, controller, lines=("¡Bienvenido, {player}!",))
    _publish(events, "[13:29:10] [Server thread/INFO]: Ana_01 joined the game")
    assert "¡Bienvenido, Ana_01!" in controller.sent[0]


def test_chat_text_cannot_trigger_the_greeting():
    events, controller = EventManager(), FakeController()
    WelcomeMessenger(events, controller)
    _publish(events, "[13:30:00] [Server thread/INFO]: <Cristian> soy yo joined the game")
    _publish(events, "[13:30:01] [Server thread/INFO]: <Cristian> Cristian joined the game")
    assert controller.sent == []


def test_leaving_or_stopped_server_sends_nothing():
    events, controller = EventManager(), FakeController(running=False)
    WelcomeMessenger(events, controller)
    _publish(events, "[13:29:10] [Server thread/INFO]: Cristian joined the game")
    controller.running = True
    _publish(events, "[13:31:00] [Server thread/INFO]: Cristian left the game")
    assert controller.sent == []