# Copyright (c) 2021 Matt Colligan
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import functools
import math
import operator
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

import cairocffi
import numpy as np
from pywayland.server import Listener
from wlroots import ffi
from wlroots.wlr_types import Texture
from wlroots.wlr_types.keyboard import KeyboardModifier

from libqtile.log_utils import logger
from libqtile.utils import QtileError, rgb

if TYPE_CHECKING:
    from typing import Any, Callable

    from pywayland.server import Signal
    from wlroots import xwayland
    from wlroots.wlr_types import Surface, data_device_manager

    from libqtile.backend.wayland.core import Core
    from libqtile.backend.wayland.output import Output
    from libqtile.backend.wayland.window import WindowType
    from libqtile.config import Screen


class WlrQError(QtileError):
    pass


ModMasks = {
    "shift": KeyboardModifier.SHIFT,
    "lock": KeyboardModifier.CAPS,
    "control": KeyboardModifier.CTRL,
    "mod1": KeyboardModifier.ALT,
    "mod2": KeyboardModifier.MOD2,
    "mod3": KeyboardModifier.MOD3,
    "mod4": KeyboardModifier.LOGO,
    "mod5": KeyboardModifier.MOD5,
}

# from linux/input-event-codes.h
_KEY_MAX = 0x2FF
# These are mouse buttons 1-9
BTN_LEFT = 0x110
BTN_MIDDLE = 0x112
BTN_RIGHT = 0x111
SCROLL_UP = _KEY_MAX + 1
SCROLL_DOWN = _KEY_MAX + 2
SCROLL_LEFT = _KEY_MAX + 3
SCROLL_RIGHT = _KEY_MAX + 4
BTN_SIDE = 0x113
BTN_EXTRA = 0x114

buttons = [
    BTN_LEFT,
    BTN_MIDDLE,
    BTN_RIGHT,
    SCROLL_UP,
    SCROLL_DOWN,
    SCROLL_LEFT,
    SCROLL_RIGHT,
    BTN_SIDE,
    BTN_EXTRA,
]

# from drm_fourcc.h
DRM_FORMAT_ARGB8888 = 875713089


def translate_masks(modifiers: list[str]) -> int:
    """
    Translate a modifier mask specified as a list of strings into an or-ed
    bit representation.
    """
    masks = []
    for i in modifiers:
        try:
            masks.append(ModMasks[i.lower()])
        except KeyError as e:
            raise WlrQError("Unknown modifier: %s" % i) from e
    if masks:
        return functools.reduce(operator.or_, masks)
    else:
        return 0


class Painter:
    def __init__(self, core: Core):
        self.core = core

    def paint(self, screen: Screen, image_path: str, mode: str | None = None) -> None:
        try:
            with open(image_path, "rb") as f:
                image, _ = cairocffi.pixbuf.decode_to_image_surface(f.read())
        except IOError:
            logger.exception("Could not load wallpaper:")
            return

        surface = cairocffi.ImageSurface(cairocffi.FORMAT_ARGB32, screen.width, screen.height)
        with cairocffi.Context(surface) as context:
            if mode == "fill":
                context.rectangle(0, 0, screen.width, screen.height)
                context.clip()
                image_w = image.get_width()
                image_h = image.get_height()
                width_ratio = screen.width / image_w
                if width_ratio * image_h >= screen.height:
                    context.scale(width_ratio)
                else:
                    height_ratio = screen.height / image_h
                    context.translate(-(image_w * height_ratio - screen.width) // 2, 0)
                    context.scale(height_ratio)
            elif mode == "stretch":
                context.scale(
                    sx=screen.width / image.get_width(),
                    sy=screen.height / image.get_height(),
                )
            context.set_source_surface(image)
            context.paint()

            stride = surface.format_stride_for_width(cairocffi.FORMAT_ARGB32, screen.width)
            surface.flush()
            texture = Texture.from_pixels(
                self.core.renderer,
                DRM_FORMAT_ARGB8888,
                stride,
                screen.width,
                screen.height,
                cairocffi.cairo.cairo_image_surface_get_data(surface._pointer),
            )
            # mypy struggles to understand this. See: https://github.com/python/mypy/issues/11513
            outputs = [
                output for output in self.core.outputs if output.wlr_output.enabled  # type: ignore
            ]
            outputs[screen.index].wallpaper = texture


class HasListeners:
    """
    Classes can subclass this to get some convenience handlers around
    `pywayland.server.Listener`.

    This guarantees that all listeners that set up and then removed in reverse order.
    """

    def add_listener(self, event: Signal, callback: Callable) -> None:
        if not hasattr(self, "_listeners"):
            self._listeners = []
        listener = Listener(callback)
        event.add(listener)
        self._listeners.append(listener)

    def finalize_listeners(self) -> None:
        for listener in reversed(self._listeners):
            listener.remove()


class Dnd(HasListeners):
    """A helper for drag and drop functionality."""

    def __init__(self, core: Core, wlr_drag: data_device_manager.Drag):
        self.core = core
        self.wlr_drag = wlr_drag
        self._outputs: set[Output] = set()

        self.x: float = core.cursor.x
        self.y: float = core.cursor.y
        self.width: int = 0  # Set upon surface commit
        self.height: int = 0

        self.add_listener(wlr_drag.destroy_event, self._on_destroy)
        self.add_listener(wlr_drag.icon.map_event, self._on_icon_map)
        self.add_listener(wlr_drag.icon.unmap_event, self._on_icon_unmap)
        self.add_listener(wlr_drag.icon.destroy_event, self._on_icon_destroy)
        self.add_listener(wlr_drag.icon.surface.commit_event, self._on_icon_commit)

    def finalize(self) -> None:
        self.finalize_listeners()
        self.core.live_dnd = None

    def _on_destroy(self, _listener: Listener, _event: Any) -> None:
        logger.debug("Signal: wlr_drag destroy")
        self.finalize()

    def _on_icon_map(self, _listener: Listener, _event: Any) -> None:
        logger.debug("Signal: wlr_drag_icon map")
        for output in self._outputs:
            output.damage()

    def _on_icon_unmap(self, _listener: Listener, _event: Any) -> None:
        logger.debug("Signal: wlr_drag_icon unmap")
        for output in self._outputs:
            output.damage()

    def _on_icon_destroy(self, _listener: Listener, _event: Any) -> None:
        logger.debug("Signal: wlr_drag_icon destroy")

    def _on_icon_commit(self, _listener: Listener, _event: Any) -> None:
        self.width = self.wlr_drag.icon.surface.current.width
        self.height = self.wlr_drag.icon.surface.current.height
        self.position(self.core.cursor.x, self.core.cursor.y)

    def position(self, cx: float, cy: float) -> None:
        self.x = cx
        self.y = cy
        self._outputs = {o for o in self.core.outputs if o.contains(self)}
        for output in self._outputs:
            output.damage()


def get_xwayland_atoms(xwayland: xwayland.XWayland) -> dict[int, str]:
    """
    These can be used when matching on XWayland clients with wm_type.
    http://standards.freedesktop.org/wm-spec/latest/ar01s05.html#idm139870830002400
    """
    xwayland_wm_types = {
        "_NET_WM_WINDOW_TYPE_DESKTOP": "desktop",
        "_NET_WM_WINDOW_TYPE_DOCK": "dock",
        "_NET_WM_WINDOW_TYPE_TOOLBAR": "toolbar",
        "_NET_WM_WINDOW_TYPE_MENU": "menu",
        "_NET_WM_WINDOW_TYPE_UTILITY": "utility",
        "_NET_WM_WINDOW_TYPE_SPLASH": "splash",
        "_NET_WM_WINDOW_TYPE_DIALOG": "dialog",
        "_NET_WM_WINDOW_TYPE_DROPDOWN_MENU": "dropdown",
        "_NET_WM_WINDOW_TYPE_POPUP_MENU": "menu",
        "_NET_WM_WINDOW_TYPE_TOOLTIP": "tooltip",
        "_NET_WM_WINDOW_TYPE_NOTIFICATION": "notification",
        "_NET_WM_WINDOW_TYPE_COMBO": "combo",
        "_NET_WM_WINDOW_TYPE_DND": "dnd",
        "_NET_WM_WINDOW_TYPE_NORMAL": "normal",
    }

    atoms = {}
    for atom, name in xwayland_wm_types.items():
        atoms[xwayland.get_atom(atom)] = name

    return atoms


@dataclass()
class CursorState:
    """
    The surface and hotspot state of the cursor. This is tracked directly by the core so
    that the cursor can be hidden and later restored to this state at will.
    """

    surface: Surface | None = None
    hotspot: tuple[int, int] = (0, 0)
    hidden: bool = False


class Shadow(NamedTuple):
    """A single window's shadow texture and dimensions."""

    texture: Texture
    width: int
    height: int
    offset: tuple[int, int]


# Cache this?
def get_shadow_config(
    wl_shadows: dict,
) -> tuple[int, tuple[float, float, float, float], tuple[int, int]]:
    offset = wl_shadows.get("offset", (-5, -5))
    assert len(offset) == 2
    sigma = wl_shadows.get("radius", 5)
    assert isinstance(sigma, int)
    color = rgb(wl_shadows.get("color", "#00000088"))
    return sigma, color, offset


def make_kernel(bounds: int, sigma: float, opacity: float) -> np.ndarray:
    """Create a gaussian kernel."""
    ax = np.linspace(bounds, 0, bounds)
    gauss = np.exp(-0.5 * np.square(ax) / np.square(sigma))
    corner = np.multiply(gauss[:, None], gauss[None, :])
    return (corner * opacity * 255).astype(np.uint32) << np.uint32(24)

    # f = -0.5 * np.square(sigma)
    # gauss = [math.exp(i * i / f) for i in range(bounds, -1, -1)]
    # return array.array("L", (int(255 * i * j) for i in gauss for j in gauss))


def make_shadow(window: WindowType) -> Shadow | None:
    config_dict = window.qtile.config.wl_shadows
    if config_dict is None:
        return None

    try:
        sigma, (r, g, b, a), (offset_x, offset_y) = get_shadow_config(config_dict)
    except Exception:
        logger.exception("Shadows config is invalid.")
        return None

    # Get a gaussian kernel
    bounds = math.ceil(sigma * 3)
    if not bounds % 2:  # We want odd kernel dimensions so it peaks at 1 in the centre
        bounds += 1

    kernel = make_kernel(bounds, sigma, a)
    bw = window.borderwidth
    bw2 = bw * 2
    width = window.width + bounds * 2 + bw2
    height = window.height + bounds * 2 + bw2

    # Draw corners
    array = np.zeros((height, width), dtype=np.uint32)
    array[bounds:-bounds, bounds:-bounds] = (
        (np.uint32(r * 255) << np.uint32(16))
        + (np.uint32(g * 255) << np.uint32(18))
        + np.uint32(b * 255)
    )
    array[:bounds, :bounds] += kernel
    array[-bounds:, :bounds] += np.flip(kernel, axis=0)
    array[:bounds, -bounds:] += np.flip(kernel, axis=1)
    array[-bounds:, -bounds:] += np.flip(kernel)
    array[bounds:-bounds, bounds:-bounds] = kernel[-1, -1]

    # Draw edges
    top_bottom = np.repeat(kernel[:, -1:], window.width + bw2, axis=1)
    left_right = np.repeat(kernel[-1:, :], window.height + bw2, axis=0)
    array[:bounds, bounds:-bounds] += top_bottom
    array[-bounds:, bounds:-bounds] += np.flipud(top_bottom)
    array[bounds:-bounds, :bounds] += left_right
    array[bounds:-bounds:, -bounds:] += np.fliplr(left_right)

    # Convert to wlr_texture
    texture = Texture.from_pixels(
        window.core.renderer,
        DRM_FORMAT_ARGB8888,
        array.ctypes.strides[0],
        width,
        height,
        ffi.cast("void*", array.ctypes.data),
    )

    return Shadow(texture, width, height, (offset_x - bounds - bw, offset_y - bounds - bw))
