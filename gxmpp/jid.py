# jid.py implements RFC 7622 and XEP-0106
import socket
from collections import namedtuple
from functools import lru_cache

import idna
import precis_i18n

from gxmpp.util.decos import reify

_UsernameCaseMapped = precis_i18n.get_profile("UsernameCaseMapped")
_OpaqueString = precis_i18n.get_profile("OpaqueString")
UnescapedJID = namedtuple("UnescapedJID", "local domain resource")


def _normalize_localpart(local):
    if local is None:
        return None
    try:
        local = _UsernameCaseMapped.enforce(local)
    except UnicodeDecodeError as e:
        raise ValueError(
            "localpart failed to validate against UsernameCaseMapped PRECIS class"
        ) from e
    l = len(local.encode("utf-8"))
    if not l or l > 1023:
        raise ValueError(
            "localpart must not be zero or exceed 1023 octets in length")
    return local


def _normalize_resourcepart(resource):
    if resource is None:
        return None
    try:
        resource = _OpaqueString.enforce(resource)
    except UnicodeDecodeError as e:
        raise ValueError(
            "resourcepart failed to validate against OpaqueString PRECIS class"
        ) from e
    l = len(resource.encode("utf-8"))
    if not l or l > 1023:
        raise ValueError(
            "resourcepart must not be zero or exceed 1023 in length")
    return resource


def _normalize_domainpart(domain):
    if domain is None:
        return None
    try:
        socket.inet_pton(socket.AF_INET, domain)
        return domain
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, domain.strip("[]"))
        return domain
    except OSError:
        pass
    if domain[-1] == ".":
        domain = domain[:-1]
    try:
        domain = idna.encode(domain)
    except idna.IDNAError as e:
        raise ValueError("domainpart must be a valid IDN string") from e
    if not domain or len(domain) > 1023:
        raise ValueError(
            "domainpart must not be zero or exceed 1023 octets in length")
    return domain.decode("utf-8")


_XEP_0106_ESCAPE = {
    " ": r"\20",
    '"': r"\22",
    "&": r"\26",
    "'": r"\27",
    "/": r"\2f",
    ":": r"\3a",
    "<": r"\3c",
    ">": r"\3e",
    "@": r"\40",
    "\\": r"\5c",
}
_XEP_0106_ESCAPE_SEQ = set(_XEP_0106_ESCAPE.keys())
_XEP_0106_UNESCAPE = dict(((v, k) for k, v in _XEP_0106_ESCAPE.items()))


def _escape_localpart(local):
    if local is None:
        return None
    if local[0] == " " or local[-1] == " ":
        raise ValueError(
            "localpart must not start or end with the SPACE character (0x20)"
        )
    es = ""
    i = 0
    m = len(local)
    while i < m:
        c = local[i]
        es += _XEP_0106_ESCAPE.get(c, c)
        i += 1
    return es


def _unescape_localpart(local):
    un = ""
    i = 0
    m = len(local)
    seq = ""
    while i < m:
        c = local[i]
        ls = len(seq)
        if ls:
            seq += c
            if ls == 2:
                un += _XEP_0106_UNESCAPE.get(seq, seq)
                seq = ""
            i += 1
            continue
        if c == "\\":
            seq = "\\"
        else:
            un += c
        i += 1
    return un


class JID:
    # TODO: it'd be worthwhile adding __slots__
    # but for the time being, I can't be arsed to figure out
    # a C(ython, probably) implementation of reify, so it'll
    # have to wait. Oh well!
    """
    A JID. JID objects are immutable and their creation is cached.
    """

    def __init__(self, local, domain, resource=None):
        """
        Create a JID from escaped parts.
        """
        if not domain:
            raise ValueError("domainpart cannot be empty or None")
        object.__setattr__(self, "local", local)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "resource", resource)

    @classmethod
    @lru_cache(maxsize=1024)
    def parse(cls, escaped):
        """
        Parse a JID from an escaped string. This method does NOT validate the JID
        """
        try:
            rest, resource = escaped.split("/", 1)
        except ValueError:
            rest = escaped
            resource = None
        try:
            local, domain = rest.split("@", 1)
        except ValueError:
            domain = rest
            local = None
        return cls(local, domain, resource)

    @classmethod
    @lru_cache(maxsize=128)
    def create(cls, local, domain, resource=None):
        """
        Create a JID from unescaped parts. This method validates the JID.
        """
        return cls(
            local=_normalize_localpart(_escape_localpart(local)),
            domain=_normalize_domainpart(domain),
            resource=_normalize_resourcepart(resource),
        )

    @reify
    def bare(self):
        """
        Form a bare JID. A bare JID is a JID without its resourcepart.
        """
        if self.local is not None:
            return self.local + "@" + self.domain
        return self.domain

    @reify
    def unescaped(self):
        """
        Unescape a JID. The result of this method is not an instance
        of the JID class and is only suitable for presentation to a
        human user or for gatewaying to a non-XMPP system. An unescaped
        JID must not be used for comparison purposes or in creation of
        XML stanzas to be sent to another network entity.
        """
        return UnescapedJID(_unescape_localpart(self.local), self.domain, self.resource)

    def __repr__(self):
        return "<JID {} at {}>".format(str(self), hex(id(self)))

    def __str__(self):
        s = ""
        if self.local is not None:
            s += self.local + "@"
        s += self.domain
        if self.resource is not None:
            s += "/" + self.resource
        return s

    def __eq__(self, other):
        if self is other:
            return True
        elif not isinstance(other, JID):
            return False
        return (
            self.local == other.local and
            idna.encode(self.domain) == idna.encode(other.domain) and
            self.resource == other.resource
        )

    def __hash__(self):
        return hash((self.local, idna.encode(self.domain), self.resource))

    def __setattr__(self, name, value):
        if name not in self.__dict__:
            raise AttributeError("'{}' object has no attribute '{}'".format(
                self.__class__.__name__, name))
        raise AttributeError("can't set attribute")
