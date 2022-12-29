# Copyright (c) 2021 Jeroen Wijenbergh
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
import pytest

import libqtile
from libqtile import config
from libqtile.backend.x11 import xcbq
from libqtile.backend.x11.core import Core
from libqtile.confreader import Config
from libqtile.lazy import lazy


@lazy.swallow
def increment_swallow(qtile):
    # Every time the command is called, this counter is incremented
    qtile.test_data += 1


# Config with multiple keys and swallow parameters
class SwallowConfig(Config):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        @libqtile.hook.subscribe.startup
        def _():
            libqtile.qtile.test_data = 0

    keys = [
        config.Key(
            ["control"],
            "k",
            increment_swallow,
        ),
        config.Key(["control"], "j", increment_swallow, swallow=False),
        config.Key(["control"], "i", increment_swallow.when(layout="idonotexist")),
        config.Key(
            ["control"],
            "o",
            increment_swallow.when(layout="idonotexist"),
            increment_swallow,
        ),
    ]

    mouse = [
        config.Click(
            [],
            "Button1",
            increment_swallow,
        ),
        config.Click(["control"], "Button3", increment_swallow, swallow=False),
        config.Click(["mod4"], "Button3", increment_swallow.when(layout="idonotexist")),
        config.Click(
            [],
            "Button3",
            increment_swallow.when(layout="idonotexist"),
            increment_swallow,
        ),
    ]


# Helper to send process_key_event to the core manager
# It also looks up the keysym and mask to pass to it
def send_process_key_event(manager, key):
    keysym, mask = Core.lookup_key(None, key)
    output = manager.c.eval(f"self.process_key_event({keysym}, {mask})[1]")
    # Assert if eval successful
    assert output[0]
    # Convert the string to a bool
    return output[1] == "True"


# Helper to send process_button_click to the core manager
# It also looks up the button code and mask to pass to it
def send_process_button_click(manager, mouse):
    modmask = xcbq.translate_masks(mouse.modifiers)
    output = manager.c.eval(
        f"self.process_button_click({mouse.button_code}, {modmask}, {0}, {0})"
    )
    # Assert if eval successful
    assert output[0]
    # Convert the string to a bool
    return output[1] == "True"


@pytest.mark.parametrize("manager", [SwallowConfig], indirect=True)
def test_swallow(manager):
    # The first key needs to be True as swallowing is not set here
    # We expect the second key to not be handled, as swallow is set to False
    # The third needs to not be swallowed as the layout .when(...) check does not succeed
    # The fourth needs to be True as one of the functions is executed due to passing the .when(...) check
    expectedswallow = [True, False, False, True]

    # Loop over all the keys in the config and assert
    for index, key in enumerate(SwallowConfig.keys):
        assert send_process_key_event(manager, key) == expectedswallow[index]

    # Loop over all the mouse bindings in the config and assert
    for index, binding in enumerate(SwallowConfig.mouse):
        assert send_process_button_click(manager, binding) == expectedswallow[index]

    not_used_key = config.Key(
        ["control"],
        "h",
        increment_swallow,
    )

    not_used_mouse = config.Click(
        [],
        "Button2",
        increment_swallow,
    )

    # This key is not defined in the config so it should not be handled
    assert not send_process_key_event(manager, not_used_key)

    # This mouse binding is not defined in the config so it should not be handled
    assert not send_process_button_click(manager, not_used_mouse)
