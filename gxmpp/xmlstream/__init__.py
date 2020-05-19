# TODO: write socket mocking lib
# since mocket doesn't quite work
# oh well!
import sys
from abc import ABC, abstractmethod

import gevent
from gevent import event, queue
from lxml import etree

from gxmpp.util import reraise

MAX_EVENT_QUEUE = 512
MAX_RECV_BUF = 2 ** 16


class ParseTarget:
    __slots__ = ("stream", "depth", "root", "current")

    def __init__(self, stream):
        self.stream = stream
        self.depth = 0
        self.root = None
        self.current = etree.TreeBuilder()

    def start(self, tag, attrib):
        if self.depth == 0:
            self.root = etree.Element(tag, attrib)
            self.stream.handle_stream_start(self.root)
        self.depth += 1
        self.current.start(tag, attrib)

    def end(self, tag):
        self.depth -= 1
        if self.depth == 0:
            self.stream.handle_stream_end()
            return
        if self.depth == 1:
            self.stream.handle_element(self.current.end(tag))
        else:
            self.current.end(tag)

    def data(self, data):
        if self.depth <= 1:
            return  # TODO: check spec?
        self.current.data(data)

    # def comment(self, text): pass

    def close(self):
        self.depth = 0
        self.root = None
        self.current = None
        self.stream.handle_close()


# XXX: NOT GREENLET-SAFE
class BaseXMLStream(ABC):
    __slots__ = ("__parser",)

    def __init__(self):
        self.__parser = etree.XMLParser(target=ParseTarget(self))

    def _feed(self, data):
        try:
            self.__parser.feed(data)
        except etree.ParseError:
            self.handle_parse_error(*sys.exc_info())

    @abstractmethod
    def handle_stream_start(self, elem):
        pass  # pragma: no cover

    @abstractmethod
    def handle_element(self, elem):
        pass  # pragma: no cover

    @abstractmethod
    def handle_parse_error(self, exc_type, exc_value, exc_traceback):
        pass  # pragma: no cover

    @abstractmethod
    def handle_stream_end(self):
        pass  # pragma: no cover

    @abstractmethod
    def handle_close(self):
        pass  # pragma: no cover


class XMLStream(BaseXMLStream):
    __slots__ = ("sock", "started", "_events", "_shutdown", "_exc_info", "_running")

    def __init__(self):
        super().__init__()
        self.sock = None
        self.started = False
        # ...
        self._events = queue.Queue(MAX_EVENT_QUEUE)
        self._shutdown = event.Event()
        self._exc_info = None
        self._running = False

    def run(self, once=False, timeout=None):
        if timeout and not once:
            raise RuntimeError("using a receive timeout value without once=True")

        try:
            return self._events.get_nowait()
        except queue.Empty:
            pass

        if self._running:
            raise RuntimeError("already running")
        self._running = True
        try:
            while not self._shutdown.is_set():
                # TODO: we might need to iwait for a shutdown event?
                # though realistically nothing outside methods invoked by
                # _feed -> XMLParser sets _shutdown so?
                buf = gevent.with_timeout(timeout, self.sock.recv, MAX_RECV_BUF)
                if not buf:
                    break
                self._feed(buf)
                if not once:
                    continue
                try:
                    return self._events.get_nowait()
                except queue.Empty:
                    continue
            exc_info = self.reset()
            if exc_info:
                reraise(*exc_info)
            return None
        finally:
            self._running = False

    def reset(self):
        self.started = False
        while True:
            try:
                self._events.get_nowait()
            except queue.Empty:
                break
        self._shutdown.clear()
        self._running = False
        exc_info = self._exc_info
        self._exc_info = None
        return exc_info

    def handle_stream_start(self, elem):
        self.started = True

    def handle_element(self, elem):
        try:
            self._events.put_nowait(elem)
        except queue.Full:
            raise RuntimeError(
                "Event queue exceeded {} items".format(MAX_EVENT_QUEUE)
            )

    def handle_parse_error(self, exc_type, exc_value, exc_traceback):
        self._shutdown.set()
        self._exc_info = (exc_type, exc_value, exc_traceback)

    def handle_stream_end(self):
        self._shutdown.set()

    def handle_close(self):
        # XXX: we *probably* don't care as exceptions thrown by the parser
        # are handled up the chain in handle_parser_error()
        # we reset in run()
        pass
