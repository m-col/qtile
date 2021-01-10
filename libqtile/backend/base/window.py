import enum
import inspect
import traceback
from abc import ABCMeta

from libqtile.log_utils import logger


class FloatState(enum.Enum):
    NOT_FLOATING = 1
    FLOATING = 2
    MAXIMIZED = 3
    FULLSCREEN = 4
    TOP = 5
    MINIMIZED = 6


def _geometry_getter(attr):
    def get_attr(self):
        if getattr(self, "_" + attr) is None:
            g = self.window.get_geometry()
            # trigger the geometry setter on all these
            self.x = g.x
            self.y = g.y
            self.width = g.width
            self.height = g.height
        return getattr(self, "_" + attr)
    return get_attr


def _geometry_setter(attr):
    def f(self, value):
        if not isinstance(value, int):
            frame = inspect.currentframe()
            stack_trace = traceback.format_stack(frame)
            logger.error("!!!! setting %s to a non-int %s; please report this!", attr, value)
            logger.error(''.join(stack_trace[:-1]))
            value = int(value)
        setattr(self, "_" + attr, value)
    return f


def _float_getter(attr):
    def getter(self):
        if self._float_info[attr] is not None:
            return self._float_info[attr]

        # we don't care so much about width or height, if not set, default to the window width/height
        if attr in ('width', 'height'):
            return getattr(self, attr)

        raise AttributeError("Floating not yet configured yet")
    return getter


def _float_setter(attr):
    def setter(self, value):
        self._float_info[attr] = value
    return setter


class Window(metaclass=ABCMeta):
    """Base class for all backend-specific window implementations."""
    def __init__(self, qtile, wid):
        self.qtile = qtile
        self.wid = wid

    x = property(fset=_geometry_setter("x"), fget=_geometry_getter("x"))
    y = property(fset=_geometry_setter("y"), fget=_geometry_getter("y"))
    width = property(fset=_geometry_setter("width"), fget=_geometry_getter("width"))
    height = property(fset=_geometry_setter("height"), fget=_geometry_getter("height"))
    float_x = property(fset=_float_setter("x"), fget=_float_getter("x"))
    float_y = property(fset=_float_setter("y"), fget=_float_getter("y"))
    float_width = property(fset=_float_setter("width"), fget=_float_getter("width"))
    float_height = property(fset=_float_setter("height"), fget=_float_getter("height"))

    @property
    def has_focus(self):
        return self == self.qtile.current_window
