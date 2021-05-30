from libqtile.backend import get_core


def test_get_core_wayland(headless):
    get_core('wayland').finalize()


from pywayland.server import Display
from wlroots.backend import Backend, BackendType

def test_wayland(headless):
    with Display() as display:
        with Backend(display):
            pass

def test_wayland2(headless):
    with Display() as display:
        with Backend(display, backend_type=BackendType.HEADLESS):
            pass
