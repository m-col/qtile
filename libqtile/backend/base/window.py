from abc import ABCMeta


class Window(metaclass=ABCMeta):
    """Base class for all backend-specific window implementations."""
    def __init__(self, qtile, wid):
        self.qtile = qtile
        self.wid = wid
