import itertools
import random
import warnings

import dns.rdatatype
import dns.resolver
from gevent import socket

from gxmpp.util.log import Log


class ServerPicker:
    def __init__(self, resolver, priority_groups):
        self._resolver = resolver
        self._priority_groups = priority_groups
        self._current_group = self.PriorityGroup([])

    @classmethod
    def from_srv_answer(cls, resolver, answer):
        prios = []
        for k, g in itertools.groupby(
            sorted(answer, key=lambda s: (s.priority, s.weight), reverse=True),
            key=lambda s: s.priority,
        ):
            entries = []
            total_weight = 0
            for entry in g:
                entries.append(entry)
                total_weight += entry.weight
            prios.append(
                ServerPicker.PriorityGroup(entries=entries, total_weight=total_weight)
            )
        return cls(resolver, prios)

    def __iter__(self):
        return self

    def __next__(self):
        if not self._current_group.entries:
            try:
                self._current_group = self._priority_groups.pop(0)
            except IndexError:
                raise StopIteration()
        choice = -1
        if self._current_group.total_weight > 0:
            rweight = random.randint(1, self._current_group.total_weight)
            sweight = 0
            for i, entry in enumerate(self._current_group.entries):
                sweight += entry.weight
                if sweight >= rweight:
                    choice = i
                    break
        else:  # only 0-weighed targets remain
            choice = random.randint(0, len(self._current_group.entries) - 1)
        if choice == -1:
            warnings.warn("__next__ failed to pick a server?")
            choice = 0
        rec = self._current_group.entries.pop(choice)
        self._current_group.total_weight -= rec.weight
        resolved = self._resolver.resolveaddrs(rec.target)
        try:
            ipv4, ipv6 = resolved.pop()
            return ipv4, ipv6, rec.port
        except IndexError:
            return next(self)  # FIXME: yeaaah, this is no good

    class PriorityGroup:
        def __init__(self, entries, total_weight=0):
            self.entries = entries
            self.total_weight = total_weight


class Resolver(Log):
    def __init__(self, service_name, service_proto="tcp", resolver=None):
        self.service_prefix = "_" + service_name + "._" + service_proto + "."
        self._resolver = resolver or dns.resolver.get_default_resolver()

    def getaddrs(self, host, port=None):
        ipv4, ipv6 = self._try_inet(host)
        if ipv4 or ipv6:
            return iter([(ipv4, ipv6, port)])

        ans = self._query(self.service_prefix + host, dns.rdatatype.SRV)
        if not ans:
            return map(lambda ph: (ph[0], ph[1], port), self.resolveaddrs(host))

        return ServerPicker.from_srv_answer(self, ans)

    def resolveaddrs(self, qname):
        def map_address_pair(p):
            ipv4, ipv6 = p
            if ipv4:
                ipv4 = ipv4.address
            if ipv6:
                ipv6 = ipv6.address
            return ipv4, ipv6

        return list(
            map(
                map_address_pair,
                itertools.zip_longest(
                    self._query(qname, dns.rdatatype.A),
                    self._query(qname, dns.rdatatype.AAAA),
                ),
            )
        )

    def _try_inet(self, host):
        host = host.strip("[]")
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return None, host
        except OSError:
            pass

        try:
            socket.inet_pton(socket.AF_INET, host)
            return host, None
        except OSError:
            pass

        return None, None

    def _query(self, qname, *args, **kwargs):
        kwargs.setdefault("raise_on_no_answer", True)
        rdtype = kwargs.get("rdtype", 1)
        rdtype_s = dns.rdatatype.to_text(rdtype)
        try:
            return self._resolver.query(qname, *args, **kwargs)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            self.log.debug("_query: missing %s record for %s", rdtype_s, qname)
        except dns.exception.Timeout:
            self.log.warning(
                "_query: timed out while querying %s record for %s", rdtype_s, qname
            )
        except dns.exception.DNSException:
            self.log.error(
                "_query: DNS failed while querying %s record for %s",
                rdtype_s,
                qname,
                exc_info=True,
            )
        return []  # FIXME: kinda nasty but oh well
