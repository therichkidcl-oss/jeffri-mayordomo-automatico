"""Decide cuando cambiar de sesion seguida y cuando anunciarlo en Telegram.

Resuelve dos problemas:

1. Flip-flop: `detect_active_session` devuelve el .jsonl con mtime mas reciente.
   Cuando dos proyectos tienen mtimes muy cercanos, la sesion "activa" alterna
   A<->B en cada lectura y disparaba un aviso cada vez. Aqui exigimos que una
   sesion aparezca `stability` lecturas SEGUIDAS antes de comprometer el cambio.

2. Pausa: si el usuario mando /parar, no se debe anunciar NADA. El seguimiento
   se actualiza por dentro (para que /seguir reanude en la sesion correcta) pero
   sin mandar el aviso "Cambie el seguimiento".
"""

from pathlib import Path


class SessionTracker:
    def __init__(self, stability: int = 2) -> None:
        self.stability = max(1, stability)
        self.current: Path | None = None
        self._candidate: Path | None = None
        self._count = 0

    def observe(self, active: Path | None, paused: bool) -> Path | None:
        """Procesa una lectura de la sesion activa.

        Devuelve la sesion a ANUNCIAR por Telegram, o None si no hay que avisar.
        Actualiza `self.current` cuando el cambio se compromete (aunque sea en
        pausa, en cuyo caso cambia en silencio y devuelve None).
        """
        if active is None:
            return None

        # Contador de estabilidad: cuenta lecturas consecutivas de la misma sesion.
        if active == self._candidate:
            self._count += 1
        else:
            self._candidate = active
            self._count = 1

        if self._count < self.stability:
            return None  # aun no es estable, no tocar nada

        if active == self.current:
            return None  # ya la seguimos, nada que hacer

        previous = self.current
        self.current = active  # compromete el cambio (para /seguir correcto)

        if previous is None:
            return None  # primera sesion detectada: seguir sin anunciar
        if paused:
            return None  # en pausa: cambia el seguimiento en silencio

        return active
