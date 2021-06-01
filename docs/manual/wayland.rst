=====================================
Running Qtile as a Wayland Compositor
=====================================

.. _wayland:


Some functionality may not yet be implemented in the Wayland compositor. Please
see the discussion `here <https://github.com/qtile/qtile/discussions/2409>`_ to
see the current state of development.

Backend-Specific Configuration
==============================

If you want your config file to work with different backends but want some
options set differently per backend, you can check the name of the current
backend in your config as follows:

.. code-block:: python

   from libqtile import qtile

   if qtile.core.name == "x11":
       term = "urxvt"
   elif qtile.core.name == "wayland":
       term = "foot"

Running X11-Only Programs
=========================

Qtile does not support XWayland directly and there are no plans to implement
XWayland support. Instead, the recommended way to run any programs that do not
support Wayland themselves is to run them inside the `cage
<https://github.com/Hjdskes/cage>`_ Wayland compositor, which will contain the
program inside a window that does support XWayland. Otherwise, you could find
alternatives that support Wayland directly.

Input Device Configuration
==========================

.. qtile_class:: libqtile.backend.wayland.input.InputConfig

If you want to change keyboard configuration during runtime, you can use the
core's `set_keymap` command (see below).

Core Commands
=============

.. qtile_class:: libqtile.backend.wayland.core.Core
