import os
import pytest

from libqtile.backend.wayland.core import Core


wlr_env = {
    "WLR_BACKENDS": "headless",
    "WLR_HEADLESS_OUTPUTS": "1",
    "WLR_LIBINPUT_NO_DEVICES": "1",
    "WLR_RENDERER_ALLOW_SOFTWARE": "1",
    "WLR_RENDERER": "pixman",
}


@pytest.fixture(scope="session")
def headless():
    old_env = os.environ.copy()
    os.environ.update(wlr_env)
    yield
    os.environ = old_env


@pytest.fixture
def wayland(headless):
    core = Core()
    yield core
    core.finalize()
