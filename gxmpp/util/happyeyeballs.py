# No matter where you go, everyone is connected.
# TODO: tests

import errno
import ipaddress
import logging

import gevent
from gevent import event, pool, queue, socket, time

RESOLVE_DELAY = 0.050  # 50 ms
CONNECT_DELAY = 0.100  # 100 ms
MIN_TIMEOUT = 0.001  # 1 ms

_log = logging.getLogger(__name__)
_no_timeout = object()


class _Cancel(Exception):
    pass


def _create_connection(
    address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None, prepare=None
):
    # Taken from:
    # https://github.com/python/cpython/blob/0f40482fde59ff307569fa5676183dd8432809a8/Lib/socket.py#L771
    # Licensed under the PSFL, version 2
    # Copyright (c) 2001-now Python Software Foundation
    host, port = address
    err = None
    for res in socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        sock = None
        try:
            sock = socket(af, socktype, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            if prepare:
                prepare(sock)
            sock.connect(sa)
            # Break explicitly a reference cycle
            err = None
            return sock

        except socket.error as e:
            err = e
            if sock is not None:
                sock.close()

    if err is not None:
        try:
            raise err
        finally:
            # Break explicitly a reference cycle
            err = None
    else:
        raise socket.error("getaddrinfo returns an empty list")


# this function does, indeed, have cyclomatic complexity of 32
def create_connection(
    address,
    timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
    dns_timeout=None,
    source_address=None,
    use_happyeyeballs=True,
    prepare=None,
):
    _log.debug("create_connection %r", address)
    (host, port, *_) = address
    try:
        ipaddress.ip_address(host)
        use_happyeyeballs = False
    except ValueError:
        pass
    if not use_happyeyeballs:
        # TODO: a bit problematic we use socket's hidden timeout sentinel
        # as our default, but it hasn't changed for 12 years so we're probably
        # gonna be fine; maybe!
        return _create_connection(
            address, timeout=timeout, source_address=source_address, prepare=prepare
        )

    group = pool.Group()
    # TODO: OK, I'm gonna be honest: this system of greenlet orchestration
    # is really, uhh, let's just say not good; the proper way of implementing
    # this would be something like curio's TaskGroup: a Group that tracks the
    # completion states of its members
    # (0, (family, addr)) = success (gai)
    # (1, sock) = success (result)
    # (-1, (family, None, exc)) = fail (gai)
    # (-2, (family, addr, exc)) = fail (connect)
    bus = queue.Queue()

    def _do_gai(family, proto=0, flags=0):
        _log.debug(
            "_do_gai: started family=%s, proto=%d, flags=%s", family, proto, flags
        )
        try:
            addrs = gevent.with_timeout(
                dns_timeout,
                socket.getaddrinfo,
                host,
                port,
                family,
                socket.SOCK_STREAM,
                proto,
                flags,
            )
            _log.debug("_do_gai: finished family=%s, addrs=%r", family, addrs)
            while addrs:
                (*_, addr) = addrs.pop()
                bus.put((0, (family, addr)))
        except _Cancel:
            _log.debug("_do_gai: cancelled family=%s", family)
        except gevent.Timeout:
            bus.put(
                (-1, (family, None, socket.gaierror(-errno.ETIMEDOUT, "Timed out")))
            )
        except Exception as e:
            bus.put((-1, (family, None, e)))

    dns_attempts = 2
    group.apply_async(_do_gai, args=(socket.AF_INET6, 0, socket.AI_V4MAPPED))
    group.apply_async(_do_gai, args=(socket.AF_INET,))

    def _do_connect(family, addr):
        _log.debug("_do_connect: started family=%s, addr=%s", family, addr)
        # TODO: god I hate the flow of logic in this proc
        sock = socket.socket(family, socket.SOCK_STREAM)
        if source_address:
            sock.bind(source_address)
        if prepare:
            prepare(sock)
        try:
            sock.connect(addr)
            _log.debug(
                "_do_connect: finished family=%s, addr=%s, socket=%r",
                family,
                addr,
                sock,
            )
        except _Cancel:
            _log.debug("_do_connect: cancelled family=%s, addr=%s", family, addr)
        except Exception as e:
            bus.put((-2, (family, addr, e)))
        except:
            sock.close()
            raise
        else:
            return bus.put((1, sock))
        sock.close()

    do_later = queue.Queue()
    started_ipv6 = event.Event()

    def _laterlet():
        try:
            stagger = started_ipv6.wait(timeout=RESOLVE_DELAY)
            if stagger:
                gevent.sleep(CONNECT_DELAY)
            for cb, args, kwds in do_later:
                group.apply_async(cb, args, kwds)
        except _Cancel:
            pass

    group.apply_async(_laterlet)

    if timeout is socket._GLOBAL_DEFAULT_TIMEOUT:
        timeout = None

    started = time.monotonic()
    conn_attempts = 0
    errors = []
    t = timeout
    try:
        while True:
            # TODO: technically this is not right:
            # we take dns query times into account as timeout
            # no good; though there's no better way of solving it
            # without restructuring the entire algo
            if t is not None:
                t = max(MIN_TIMEOUT, timeout - (time.monotonic() - started))
            op, rest = bus.get(timeout=t)
            _log.debug("bus get op %d with payload %s", op, rest)
            _log.debug("error states = %r", errors)
            if op == 1:
                return rest
            elif op == -1:
                errors.append(rest)
                dns_attempts -= 1
                if dns_attempts <= 0:
                    raise socket.error(errors)
                continue
            elif op == -2:
                errors.append(rest)
                conn_attempts -= 1
                if conn_attempts <= 0:
                    raise socket.error(errors)
                continue
            family, addr = rest
            conn_attempts += 1
            if family == socket.AF_INET:
                do_later.put((_do_connect, (socket.AF_INET, addr), {}))
            else:
                started_ipv6.set()
                group.apply_async(_do_connect, (socket.AF_INET6, addr))
    except queue.Empty:
        raise socket.timeout("timed out")
    finally:
        group.kill(_Cancel)
