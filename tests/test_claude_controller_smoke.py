"""
Smoke test manual. NO se corre con pytest CI (no tiene funciones test_*).

Para probar:
1. Abre Claude Code Desktop y haz click en una sesion.
2. Ejecuta:
   - Con mensaje custom: python -m tests.test_claude_controller_smoke "tu mensaje"
   - Interactivo: python -m tests.test_claude_controller_smoke
3. Observa que el texto aparezca en el input.
"""
import asyncio
import sys
from src.claude_controller import ClaudeController, ClaudeNotOpenError, PCLockedError


async def _run(msg: str) -> int:
    ctrl = ClaudeController()
    try:
        await ctrl.send(msg)
        print("✅ Enviado")
        return 0
    except ClaudeNotOpenError as e:
        print(f"❌ {e}")
        return 1
    except PCLockedError as e:
        print(f"❌ {e}")
        return 2


def main():
    if len(sys.argv) > 1:
        msg = " ".join(sys.argv[1:])
    else:
        msg = input("Mensaje a enviar (Enter para cancelar): ").strip()
        if not msg:
            print("Cancelado.")
            sys.exit(0)
    sys.exit(asyncio.run(_run(msg)))


if __name__ == "__main__":
    main()
