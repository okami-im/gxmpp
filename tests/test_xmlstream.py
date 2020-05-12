from gevent.queue import Queue
from lxml import etree

from gxmpp.util.xml import element_eq
from gxmpp.xmlstream import XMLStream


def test_xmlstream():
    q = Queue()

    def expected(event, elem=None):
        e, el = q.get(block=False)
        assert e == event
        if elem is not None:
            assert element_eq(el, elem)

    class TestStream(XMLStream):
        def handle_stream_start(self, elem):
            q.put(("stream_start", elem))

        def handle_element(self, elem):
            q.put(("element", elem))

        def handle_parse_error(self, typ, value, tb):
            q.put(("parse_error", (typ, value, tb)))

        def handle_stream_end(self):
            q.put(("stream_end", None))

        def handle_close(self):
            q.put(("close", None))

    t = TestStream()
    t._feed("<stream key='value'>")
    expected("stream_start", etree.Element("stream", {"key": "value"}))
    e = etree.Element("message", {})
    e.append(etree.Element("body", {}))
    t._feed("<message><body></body></message>")
    expected("element", e)
    t._feed("</stream>")
    expected("stream_end")
