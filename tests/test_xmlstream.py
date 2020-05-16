import pytest
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

        def handle_parse_error(self, exc_type, exc_value, exc_traceback):
            raise exc_value.with_traceback(exc_traceback)

        def handle_stream_end(self):
            q.put(("stream_end", None))

        def handle_close(self):
            q.put(("close", None))

    t = TestStream()
    t._feed("<stream key='value'>")
    expected("stream_start", etree.Element("stream", {"key": "value"}))
    e = etree.Element("message", {})
    b = etree.Element("body", {})
    b.text = "foobar"
    e.append(b)
    t._feed("<message><body>foobar</body></message>")
    expected("element", e)
    t._feed("</stream>")
    expected("stream_end")
    with pytest.raises(etree.XMLSyntaxError, match="[eE]xtra content"):
        t._feed("</stream>")
    expected("close")
