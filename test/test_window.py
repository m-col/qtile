import os
import subprocess
import tempfile

import pytest

from libqtile import layout, utils
from test.conftest import BareConfig
from test.test_images2 import should_skip

bare_config = pytest.mark.parametrize("manager", [BareConfig], indirect=True)


@bare_config
def test_margin(manager):
    manager.test_window('one')

    # No margin
    manager.c.window.place(10, 20, 50, 60, 0, '000000')
    assert manager.c.window.info()['x'] == 10
    assert manager.c.window.info()['y'] == 20
    assert manager.c.window.info()['width'] == 50
    assert manager.c.window.info()['height'] == 60

    # Margin as int
    manager.c.window.place(10, 20, 50, 60, 0, '000000', margin=8)
    assert manager.c.window.info()['x'] == 18
    assert manager.c.window.info()['y'] == 28
    assert manager.c.window.info()['width'] == 34
    assert manager.c.window.info()['height'] == 44

    # Margin as list
    manager.c.window.place(10, 20, 50, 60, 0, '000000', margin=[2, 4, 8, 10])
    assert manager.c.window.info()['x'] == 20
    assert manager.c.window.info()['y'] == 22
    assert manager.c.window.info()['width'] == 36
    assert manager.c.window.info()['height'] == 50


class MultipleBordersConfig(BareConfig):
    layouts = [
        layout.Stack(
            border_focus=['#000000', '#111111', '#222222', '#333333', '#444444'],
            border_width=5,
        )
    ]


@pytest.mark.skipif(should_skip(), reason="recent version of imagemagick not found")
@pytest.mark.parametrize("manager", [MultipleBordersConfig], indirect=True)
def test_multiple_borders(manager):
    manager.test_window("one")
    wid = manager.c.window.info()["id"]

    name = os.path.join(tempfile.gettempdir(), 'test_multiple_borders.txt')
    cmd = ["import", "-border", "-window", str(wid), "-crop", "5x1+0+4", '-depth', '8', name]
    subprocess.run(cmd, env={"DISPLAY": manager.display})

    with open(name, 'r') as f:
        data = f.readlines()
    os.unlink(name)

    # just test that each of the 5 borders is lighter than the last as the screenshot is
    # not pixel-perfect
    avg = -1
    for i in range(5):
        color = utils.rgb(data[i + 1].split()[2])
        next_avg = sum(color) / 3
        assert avg < next_avg
        avg = next_avg
