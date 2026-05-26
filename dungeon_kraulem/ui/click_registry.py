"""Per-frame click + hover registry (P24.5).

Each frame, draw functions register their interactive rects via
`add(rect, callback, tooltip)`. The Game's mousedown / mousemotion
handlers query the registry to dispatch.

Design notes:
  * Stateless across frames. `reset()` at the start of every draw.
  * Latest-drawn-wins: registry stores items in registration order;
    `find(x, y)` walks REVERSED so an overlay (e.g. journal modal) takes
    priority over the world panels beneath it.
  * `callback` is a zero-arg callable. Keeps the registry decoupled from
    the Game class — handlers can be simple closures.
  * `tooltip` is optional plain text rendered by the hover renderer.
  * `keyboard_sync` is an optional (group_key, option_index) tuple. When
    a click commits, the Game updates `nav_state.selected_index_by_group`
    to match — keyboard/mouse cursor stays in sync as the user mentioned.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple


Rect = Tuple[int, int, int, int]


@dataclass
class ClickZone:
    rect: Rect
    callback: Callable[[], None]
    tooltip: str = ""
    keyboard_sync: Optional[Tuple[str, int]] = None
    # Optional category tag — useful for debug / hover-styling.
    category: str = ""


@dataclass
class ClickRegistry:
    zones: List[ClickZone] = field(default_factory=list)

    def reset(self) -> None:
        self.zones.clear()

    def add(self, rect: Rect, callback: Callable[[], None],
            *, tooltip: str = "", keyboard_sync=None,
            category: str = "") -> None:
        self.zones.append(ClickZone(rect=rect, callback=callback,
                                    tooltip=tooltip,
                                    keyboard_sync=keyboard_sync,
                                    category=category))

    def find(self, x: int, y: int) -> Optional[ClickZone]:
        """Return the topmost zone under (x, y), or None."""
        for z in reversed(self.zones):
            rx, ry, rw, rh = z.rect
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return z
        return None
