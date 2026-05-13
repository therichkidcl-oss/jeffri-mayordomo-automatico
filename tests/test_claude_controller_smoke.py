"""
Smoke test manual. NO se corre con pytest CI.

Para probar:
1. Abre Claude Code Desktop y haz click en una sesión.
2. Ejecuta: python -m tests.test_claude_controller_smoke
3. Observa que el texto aparezca en el input.
"""
import sys
from src.claude_controller import ClaudeController, ClaudeNotOpenError, PCLockedError


def main():
    ctrl = ClaudeController()
    try:
        ctrl.send("test desde TelegramClaudeBridge — ignora este mensaje")
        print("✅ Enviado")
    except ClaudeNotOpenError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except PCLockedError as e:
        print(f"❌ {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
