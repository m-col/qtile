# Copyright (c) 2011 Florian Mounier
# Copyright (c) 2012, 2014 Tycho Andersen
# Copyright (c) 2013 Craig Barnes
# Copyright (c) 2014 Sean Vig
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

import libqtile.bar
import libqtile.config
import libqtile.confreader
import libqtile.layout
import libqtile.widget
from libqtile.command_interface import CommandError
from libqtile.command_object import CommandObject
from libqtile.confreader import Config
from libqtile.lazy import lazy


class CallConfig(Config):
    keys = [
        libqtile.config.Key(
            ["control"], "j",
            lazy.layout.down(),
        ),
        libqtile.config.Key(
            ["control"], "k",
            lazy.layout.up(),
        ),
    ]
    mouse = []
    groups = [
        libqtile.config.Group("a"),
        libqtile.config.Group("b"),
    ]
    layouts = [
        libqtile.layout.Stack(num_stacks=1),
        libqtile.layout.Max(),
    ]
    floating_layout = libqtile.resources.default_config.floating_layout
    screens = [
        libqtile.config.Screen(
            bottom=libqtile.bar.Bar(
                [
                    libqtile.widget.GroupBox(),
                ],
                20
            ),
        )
    ]
    auto_fullscreen = True


call_config = pytest.mark.parametrize("self", [CallConfig], indirect=True)


@call_config
def test_layout_filter(self):
    self.test_window("one")
    self.test_window("two")
    assert self.c.groups()["a"]["focus"] == "two"
    self.c.simulate_keypress(["control"], "j")
    assert self.c.groups()["a"]["focus"] == "one"
    self.c.simulate_keypress(["control"], "k")
    assert self.c.groups()["a"]["focus"] == "two"


class TestCommands(CommandObject):
    @staticmethod
    def cmd_one():
        pass

    def cmd_one_self(self):
        pass

    def cmd_two(self, a):
        pass

    def cmd_three(self, a, b=99):
        pass

    def _items(self, name):
        return None

    def _select(self, name, sel):
        return None


def test_doc():
    c = TestCommands()
    assert "one()" in c.cmd_doc("one")
    assert "one_self()" in c.cmd_doc("one_self")
    assert "two(a)" in c.cmd_doc("two")
    assert "three(a, b=99)" in c.cmd_doc("three")


def test_commands():
    c = TestCommands()
    assert len(c.cmd_commands()) == 9


def test_command():
    c = TestCommands()
    assert c.command("one")
    assert not c.command("nonexistent")


class ServerConfig(Config):
    auto_fullscreen = True
    keys = []
    mouse = []
    groups = [
        libqtile.config.Group("a"),
        libqtile.config.Group("b"),
        libqtile.config.Group("c"),
    ]
    layouts = [
        libqtile.layout.Stack(num_stacks=1),
        libqtile.layout.Stack(num_stacks=2),
        libqtile.layout.Stack(num_stacks=3),
    ]
    floating_layout = libqtile.resources.default_config.floating_layout
    screens = [
        libqtile.config.Screen(
            bottom=libqtile.bar.Bar(
                [
                    libqtile.widget.TextBox(name="one"),
                ],
                20
            ),
        ),
        libqtile.config.Screen(
            bottom=libqtile.bar.Bar(
                [
                    libqtile.widget.TextBox(name="two"),
                ],
                20
            ),
        )
    ]


server_config = pytest.mark.parametrize("self", [ServerConfig], indirect=True)


@server_config
def test_cmd_commands(self):
    assert self.c.commands()
    assert self.c.layout.commands()
    assert self.c.screen.bar["bottom"].commands()


@server_config
def test_call_unknown(self):
    with pytest.raises(libqtile.command_client.SelectError, match="Not valid child or command"):
        self.c.nonexistent

    self.c.layout
    with pytest.raises(libqtile.command_client.SelectError, match="Not valid child or command"):
        self.c.layout.nonexistent


@server_config
def test_items_qtile(self):
    v = self.c.items("group")
    assert v[0]
    assert sorted(v[1]) == ["a", "b", "c"]

    assert self.c.items("layout") == (True, [0, 1, 2])

    v = self.c.items("widget")
    assert not v[0]
    assert sorted(v[1]) == ['one', 'two']

    assert self.c.items("bar") == (False, ["bottom"])
    t, lst = self.c.items("window")
    assert t
    assert len(lst) == 2
    assert self.c.window[lst[0]]
    assert self.c.items("screen") == (True, [0, 1])


@server_config
def test_select_qtile(self):
    assert self.c.layout.info()["group"] == "a"
    assert len(self.c.layout.info()["stacks"]) == 1
    assert len(self.c.layout[2].info()["stacks"]) == 3
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        self.c.layout[99]

    assert self.c.group.info()["name"] == "a"
    assert self.c.group["c"].info()["name"] == "c"
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        self.c.group["nonexistent"]

    assert self.c.widget["one"].info()["name"] == "one"
    with pytest.raises(CommandError, match="No object widget"):
        self.c.widget.info()

    assert self.c.bar["bottom"].info()["position"] == "bottom"

    self.test_window("one")
    wid = self.c.window.info()["id"]
    assert self.c.window[wid].info()["id"] == wid

    assert self.c.screen.info()["index"] == 0
    assert self.c.screen[1].info()["index"] == 1
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        self.c.screen[22]


@server_config
def test_items_group(self):
    group = self.c.group

    self.test_window("test")
    wid = self.c.window.info()["id"]

    assert group.items("window") == (True, [wid])
    assert group.items("layout") == (True, [0, 1, 2])
    assert group.items("screen") == (True, None)


@server_config
def test_select_group(self):
    group = self.c.group

    assert group.layout.info()["group"] == "a"
    assert len(group.layout.info()["stacks"]) == 1
    assert len(group.layout[2].info()["stacks"]) == 3

    with pytest.raises(CommandError):
        self.c.group.window.info()
    self.test_window("test")
    wid = self.c.window.info()["id"]

    assert group.window.info()["id"] == wid
    assert group.window[wid].info()["id"] == wid
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        group.window["foo"]

    assert group.screen.info()["index"] == 0
    assert group["b"].screen.info()["index"] == 1
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        group.screen[0]


@server_config
def test_items_screen(self):
    s = self.c.screen
    assert s.items("layout") == (True, [0, 1, 2])

    self.test_window("test")
    wid = self.c.window.info()["id"]
    assert s.items("window") == (True, [wid])

    assert s.items("bar") == (False, ["bottom"])


@server_config
def test_select_screen(self):
    screen = self.c.screen
    assert screen.layout.info()["group"] == "a"
    assert len(screen.layout.info()["stacks"]) == 1
    assert len(screen.layout[2].info()["stacks"]) == 3

    with pytest.raises(CommandError):
        self.c.window.info()

    self.test_window("test")
    wid = self.c.window.info()["id"]
    assert screen.window.info()["id"] == wid
    assert screen.window[wid].info()["id"] == wid

    with pytest.raises(CommandError, match="No object"):
        screen.bar.info()
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        screen.bar["top"]

    assert screen.bar["bottom"].info()["position"] == "bottom"


@server_config
def test_items_bar(self):
    assert self.c.bar["bottom"].items("screen") == (True, None)


@server_config
def test_select_bar(self):
    assert self.c.screen[1].bar["bottom"].screen.info()["index"] == 1
    b = self.c.bar
    assert b["bottom"].screen.info()["index"] == 0
    with pytest.raises(CommandError):
        b.screen.info()


@server_config
def test_items_layout(self):
    assert self.c.layout.items("screen") == (True, None)
    assert self.c.layout.items("group") == (True, None)


@server_config
def test_select_layout(self):
    layout = self.c.layout

    assert layout.screen.info()["index"] == 0
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        layout.screen[0]

    assert layout.group.info()["name"] == "a"
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        layout.group["a"]


@server_config
def test_items_window(self):
    self.test_window("test")
    window = self.c.window
    window.info()["id"]

    assert window.items("group") == (True, None)
    assert window.items("layout") == (True, [0, 1, 2])
    assert window.items("screen") == (True, None)


@server_config
def test_select_window(self):
    self.test_window("test")
    window = self.c.window
    window.info()["id"]

    assert window.group.info()["name"] == "a"
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        window.group["a"]

    assert len(window.layout.info()["stacks"]) == 1
    assert len(window.layout[1].info()["stacks"]) == 2

    assert window.screen.info()["index"] == 0
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        window.screen[0]


@server_config
def test_items_widget(self):
    assert self.c.widget["one"].items("bar") == (True, None)


@server_config
def test_select_widget(self):
    widget = self.c.widget["one"]
    assert widget.bar.info()["position"] == "bottom"
    with pytest.raises(libqtile.command_client.SelectError, match="Item not available in object"):
        widget.bar["bottom"]
