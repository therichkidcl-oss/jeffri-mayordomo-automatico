import asyncio

from src.voice.app import VoiceLoop
from src.voice.brain import BrainResponse


class FakeBrain:
    def __init__(self, response, summary="resumen de claude"):
        self._response = response
        self._summary = summary
        self.turns = []

    async def handle_user_turn(self, text):
        self.turns.append(text)
        return self._response

    async def summarize_claude(self, claude_text):
        return self._summary


class FakeController:
    def __init__(self):
        self.sent = []

    async def send(self, text):
        self.sent.append(text)


def _loop(brain, controller, get_claude_response=None, record=b"AUDIO", transcript="hola"):
    spoken = []
    vl = VoiceLoop(
        transcriber=lambda a: transcript,
        brain=brain,
        tts_speak=lambda t: spoken.append(t),
        controller=controller,
        send_lock=asyncio.Lock(),
        get_claude_response=get_claude_response or (lambda: _async_none()),
        record_fn=lambda hk: record,
        hotkey="f9",
    )
    return vl, spoken


async def _async_none():
    return None


def test_chat_turn_only_speaks():
    brain = FakeBrain(BrainResponse(speech="opino que si"))
    ctrl = FakeController()
    vl, spoken = _loop(brain, ctrl)
    asyncio.run(vl.process_turn())
    assert spoken == ["opino que si"]
    assert ctrl.sent == []  # no se mando nada a Claude


def test_empty_transcript_does_nothing():
    brain = FakeBrain(BrainResponse(speech="x"))
    ctrl = FakeController()
    vl, spoken = _loop(brain, ctrl, transcript="   ")
    asyncio.run(vl.process_turn())
    assert spoken == []
    assert brain.turns == []  # ni siquiera llega al cerebro


def test_dispatch_turn_sends_to_claude_and_summarizes():
    brain = FakeBrain(BrainResponse(speech="se lo mando", dispatch_prompt="Arregla el login."),
                      summary="Claude arreglo el login")
    ctrl = FakeController()

    async def get_resp():
        return "[respuesta larga de Claude sobre el login]"

    vl, spoken = _loop(brain, ctrl, get_claude_response=get_resp)
    asyncio.run(vl.process_turn())
    assert ctrl.sent == ["Arregla el login."]           # se mando el prompt
    assert "se lo mando" in spoken                        # confirma el envio
    assert "Claude arreglo el login" in spoken           # habla el resumen


def test_no_audio_skips():
    brain = FakeBrain(BrainResponse(speech="x"))
    ctrl = FakeController()
    vl, spoken = _loop(brain, ctrl, record=b"")
    asyncio.run(vl.process_turn())
    assert spoken == []
    assert brain.turns == []
