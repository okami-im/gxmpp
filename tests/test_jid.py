import pytest
from hypothesis import given
from hypothesis import strategies as strat

from gxmpp import jid


def test_parse():
    with pytest.raises(ValueError, match="domain"):
        jid.JID("INVALID", None, "JID")
    j = jid.JID.parse("d\\27artagnan@musketeers.lit/foo/bar@qux!quux")
    assert j.local == "d\\27artagnan"
    assert j.domain == "musketeers.lit"
    assert j.resource == "foo/bar@qux!quux"
    assert j.bare == "d\\27artagnan@musketeers.lit"
    assert j.unescaped == jid.UnescapedJID(
        "d'artagnan", "musketeers.lit", "foo/bar@qux!quux"
    )
    assert str(j) == "d\\27artagnan@musketeers.lit/foo/bar@qux!quux"


def test_create():
    j = jid.JID.create("John O'Hara", "writers.club.")
    assert j.local == "john\\20o\\27hara"
    assert j.domain == "writers.club"
    assert j.bare == str(j) == "john\\20o\\27hara@writers.club"
    j = jid.JID.create(None, "writers.club")
    assert j.local is None
    assert j.domain == j.bare == str(j) == "writers.club"
    jid.JID.create(None, "127.0.0.1")
    with pytest.raises(ValueError, match="SPACE"):
        jid.JID.create(" INVALID", "JID")
    with pytest.raises(ValueError, match="1023"):
        jid.JID.create("a" * 1024, "example.org", "foo/bar")
    with pytest.raises(ValueError, match="1023"):
        jid.JID.create("INVALID", "example.org", "a" * 1024)
    with pytest.raises(ValueError, match="IDN"):
        jid.JID.create("INVALID", "example\u200B.org", "foo/bar")
    with pytest.raises(ValueError, match="UsernameCaseMapped"):
        jid.JID.create("INVAL\u200BID", "example.org", "foo/bar")
    with pytest.raises(ValueError, match="OpaqueString"):
        jid.JID.create("INVALID", "example.org", "\u200B")


def test_dunders():
    j1 = jid.JID.parse("porthos@銃士.lit")
    with pytest.raises(AttributeError):
        j1.local = "d'artagnan"
    j2 = jid.JID.create("porthos", "xn--zqs335k.lit")
    assert j1 == j2
    assert hash(j1) == hash(j2)


_valid_xep_0106_ish = {
    "whitelist_categories": ("Ll", "Lu", "Lo", "Nd", "Lm", "Mn", "Mc"),
    "whitelist_characters": jid._XEP_0106_ESCAPE_SEQ,
}


@given(localpart=strat.characters(**_valid_xep_0106_ish))
def test_xep_0106(localpart):
    if (
        localpart[0] == " " or localpart[-1] == " "
    ):  # we test this one separately in test_create
        return
    assert jid._unescape_localpart(jid._escape_localpart(localpart)) == localpart
