import sys
from abc import ABC, abstractmethod

from gevent.lock import BoundedSemaphore
from lxml import etree


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


class XMLStream(ABC):
    __slots__ = ("__parser", "__feed_lock")

    def __init__(self):
        self.__parser = etree.XMLParser(target=ParseTarget(self))
        self.__feed_lock = BoundedSemaphore()

    def _feed(self, data):
        with self.__feed_lock:
            try:
                self.__parser.feed(data)
            except etree.ParseError:
                self.handle_parse_error(*sys.exc_info())

    @abstractmethod
    def handle_stream_start(self, elem):
        pass

    @abstractmethod
    def handle_element(self, elem):
        pass

    @abstractmethod
    def handle_parse_error(self, typ, value, tb):
        pass

    @abstractmethod
    def handle_stream_end(self):
        pass

    @abstractmethod
    def handle_close(self):
        pass
