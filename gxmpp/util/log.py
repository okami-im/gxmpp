import logging
import warnings

from gxmpp.util.decos import reify


def setup_logging(*args, **kwargs):
    warnings.filterwarnings("always")
    logging.captureWarnings(True)
    logging.basicConfig(*args, **kwargs)


class Log:
    @reify
    def log(self):
        return logging.getLogger(self.__class__.__qualname__)
