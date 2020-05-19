import gevent
import pytest
from gevent import queue, socket
from lxml import etree

from gxmpp.util.xml import element_eq
from gxmpp.xmlstream import BaseXMLStream, XMLStream


def test_basexmlstream():
    q = queue.Queue()

    def expected(event, elem=None):
        e, el = q.get(block=False)
        assert e == event
        if elem is not None:
            assert element_eq(el, elem)

    class TestStream(BaseXMLStream):
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


def test_xmlstream():
    # TODO: a better framework for testing stuff like this
    q = queue.Queue()
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    lsock.bind(("127.0.0.1", 0))
    addr = lsock.getsockname()

    def _server():
        with lsock:
            lsock.listen()
            conn, _ = lsock.accept()
            with conn:
                for iq in q:
                    op, data = iq
                    if op != 0:
                        break
                    conn.sendall(data)

    serverlet = gevent.spawn(_server)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(addr)
        x = XMLStream()
        x.sock = sock
        q.put((0, b"<stream><message/><message/>"))
        e = x.run(once=True)
        assert x.started
        assert e.tag == "message"
        e = x.run(once=True)
        assert e.tag == "message"
        q.put((0, b"</stream>"))
        assert not x.run(once=True)
        q.put((1, b""))
        assert not x.run(once=True)
    finally:
        serverlet.kill()
