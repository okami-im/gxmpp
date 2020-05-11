# TODO: tests

from itertools import groupby
from random import randint
from warnings import warn

import dns.rdatatype
import dns.resolver
from gevent import socket

from gxmpp.util.log import Log


class ResolverError(Exception):
    pass


class Resolver(Log):
    def __init__(self, service_template, resolver, prefer_ipv6):
        self._tmpl = service_template
        self._resolver = resolver
        self._prefer_ipv6 = prefer_ipv6

    def getaddrs(self, host, port=None):
        inet = self._try_inet(host)
        if inet:
            return iter([(inet, port)])

        srvhost = self._tmpl + host
        try:
            answer = self._resolver.query(srvhost, dns.rdatatype.SRV)
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            self.log.debug("getaddrs: missing SRV record for %s", srvhost)
        except dns.exception.Timeout:
            self.log.warning(
                "getaddrs: timed out while querying SRV record for %s", srvhost)
        except dns.exception.DNSException:
            self.log.error(
                "getaddrs: DNS failed while querying SRV record for %s", srvhost, exc_info=True)
        else:
            prios = []
            for k, g in groupby(sorted(answer, key=lambda s: (s.priority, s.weight), reverse=True), key=lambda s: s.priority):
                entries = []
                total_weight = 0
                for entry in g:
                    entries.append(entry)
                    total_weight += entry.weight
                prios.append(self._PriorityGroup(
                    entries=entries, total_weight=total_weight))
            return self._ServerPicker(self, prios)
        return map(lambda h: (h, port), self.resolveaddr(host))

    def resolveaddr(self, host):
        tried_ipv6 = False
        if self._prefer_ipv6:
            tried_ipv6 = True
            ipv6 = self._try_ipv6(host)
            if ipv6:
                return ipv6
        ipv4 = self._try_ipv4(host)
        if ipv4:
            return ipv4
        if not tried_ipv6:
            ipv6 = self._try_ipv6(host)
            if ipv6:
                return ipv6
        raise ResolverError("failed to resolve: {}".format(host))

    def _try_ipv6(self, host):
        try:
            return map(lambda r: r.address, self._resolver.query(host, dns.rdatatype.AAAA))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            self.log.debug("_try_ipv6: missing AAAA record for %s", host)
        except dns.exception.Timeout:
            self.log.warning(
                "_try_ipv6: timed out while querying AAAA record for %s", host)
        except dns.exception.DNSException:
            self.log.error(
                "_try_ipv6: DNS failed while querying AAAA record for %s", host, exc_info=True)
        return None

    def _try_ipv4(self, host):
        try:
            return map(lambda r: r.address, self._resolver.query(host, dns.rdatatype.A))
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            self.log.debug("_try_ipv6: missing A record for %s", host)
        except dns.exception.Timeout:
            self.log.warning(
                "_try_ipv6: timed out while querying A record for %s", host)
        except dns.exception.DNSException:
            self.log.error(
                "_try_ipv6: DNS failed while querying A record for %s", host, exc_info=True)
        return None

    def _try_inet(self, host):
        try:
            socket.inet_pton(socket.AF_INET, host)
            return host
        except OSError:
            pass

        host = host.strip('[]')
        try:
            socket.inet_pton(socket.AF_INET6, host)
            return host
        except OSError:
            pass

        return None

    class _PriorityGroup(list):  # TODO
        def __init__(self, entries, total_weight):
            super().__init__(entries)
            self.total_weight = total_weight

    class _ServerPicker:
        def __init__(self, resolver, priority_groups):
            self._resolver = resolver
            self._priority_groups = priority_groups
            self._current_group = resolver._PriorityGroup(
                entries=[], total_weight=0)

        def __iter__(self):
            return self

        def __next__(self):
            if not self._current_group:
                try:
                    self._current_group = self._priority_groups.pop(0)
                except IndexError:
                    raise StopIteration()
            choice = -1
            if self._current_group.total_weight > 0:
                rweight = randint(1, self._current_group.total_weight)
                sweight = 0
                for i, entry in enumerate(self._current_group):  # TODO: optimize
                    sweight += entry.weight
                    if sweight >= rweight:
                        choice = i
                        break
            else:  # only 0-weighed targets remain
                choice = randint(0, len(self._current_group) - 1)
            if choice == -1:
                warn("__next__ failed to pick a server?")
                choice = 0
            rec = self._current_group.pop(choice)
            self._current_group.total_weight -= rec.weight
            return list(self._resolver.resolveaddr(rec.target)), rec.port
