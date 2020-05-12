import functools


# NOTE: Taken from
# https://github.com/Pylons/pyramid/blob/bda1306749c62ef4f11cfe567ed7d56c8ad94240/src/pyramid/decorator.py  # noqa:B950
# License: Zope Public License (ZPL) Version 2.1
class reify:  # noqa:N801
    def __init__(self, wrapped):
        functools.update_wrapper(self, wrapped)
        self.wrapped = wrapped

    def __get__(self, this, cls):
        if this is None:
            return self
        val = self.wrapped(this)
        object.__setattr__(this, self.wrapped.__name__, val)
        return val


class slot_reify:  # noqa:N801
    def __init__(self, wrapped):
        functools.update_wrapper(self, wrapped)
        self.wrapped = wrapped
        self.slot = "_" + wrapped.__name__

    def __get__(self, this, cls):
        if this is None:
            return self
        slot = cls.__dict__[self.slot]
        try:
            return slot.__get__(this)
        except AttributeError:
            val = self.wrapped(this)
            slot.__set__(this, val)
            return val
