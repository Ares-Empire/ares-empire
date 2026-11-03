"""Request reading and worker limits shared by the hub and push listeners."""

import io
import ipaddress
import os
import re
import threading
from collections import OrderedDict
from http.server import ThreadingHTTPServer
from time import monotonic

HEADER_SECONDS = 5
BODY_SECONDS = 5
WRITE_SECONDS = 5
MAX_BODY_BYTES = 10_000


def address(value):
    try:
        parsed = ipaddress.ip_address(value)
        return str(parsed.ipv4_mapped if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped else parsed)
    except ValueError:
        return ""


def trusted_proxies():
    return {address(item.strip()) for item in os.environ.get("AUTH_TRUSTED_PROXY", "127.0.0.1,::1").split(",")
            if address(item.strip())}


class ClientLimits:
    """Per-client concurrency and a token bucket, with bounded bookkeeping."""

    def __init__(self, concurrent=8, rate=4, burst=80, clock=monotonic):
        self.concurrent = concurrent
        self.rate = rate
        self.burst = burst
        self.clock = clock
        self.clients = OrderedDict()
        self.lock = threading.Lock()

    def acquire(self, client):
        now = self.clock()
        with self.lock:
            if client not in self.clients:
                if len(self.clients) >= 4096:
                    unused = next((key for key, state in self.clients.items() if not state[0]), None)
                    if unused is None:
                        return 503
                    del self.clients[unused]
                self.clients[client] = [0, self.burst, now]
            state = self.clients[client]
            self.clients.move_to_end(client)
            state[1] = min(self.burst, state[1] + max(0, now - state[2]) * self.rate)
            state[2] = now
            if state[1] < 1:
                return 429
            state[1] -= 1
            if state[0] >= self.concurrent:
                return 503
            state[0] += 1
            return 0

    def release(self, client):
        with self.lock:
            self.clients[client][0] -= 1


class DeadlineReader(io.RawIOBase):
    """A buffered input's reads share one absolute deadline."""

    def __init__(self, source, connection):
        self.source = source
        self.connection = connection
        self.deadline = monotonic() + HEADER_SECONDS

    def readable(self):
        return True

    def readinto(self, target):
        remaining = self.deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Request read deadline reached")
        self.connection.settimeout(remaining)
        data = self.source.read1(len(target))
        target[:len(data)] = data
        return len(data)

    def close(self):
        self.source.close()
        super().close()


class LimitedRequestHandler:
    """Limits the body before reading it, then hands complete input to the route."""

    def setup(self):
        super().setup()
        self.request_input = DeadlineReader(self.rfile, self.connection)
        self.rfile = io.BufferedReader(self.request_input)

    def handle_one_request(self):
        self.request_input.deadline = monotonic() + HEADER_SECONDS
        self.admitted_client = None
        try:
            super().handle_one_request()
        finally:
            if self.admitted_client is not None:
                self.server.client_limits.release(self.admitted_client)

    def request_client_ip(self):
        peer = address(self.client_address[0])
        proxies = self.server.trusted_proxies if isinstance(self.server, LimitedHTTPServer) else trusted_proxies()
        forwarded = self.headers.get_all("X-Forwarded-For", [])
        if peer in proxies and len(forwarded) == 1:
            return address(forwarded[0].split(",")[-1].strip()) or peer
        return peer

    def parse_request(self):
        if not super().parse_request():
            return False
        self.close_connection = True
        self.request_body = b""
        if isinstance(self.server, LimitedHTTPServer) and self.server.client_limits is not None:
            client = self.request_client_ip()
            status = self.server.client_limits.acquire(client)
            if status:
                return self.reject_request(status, "Too many requests. Please try again shortly.")
            self.admitted_client = client
        lengths = self.headers.get_all("Content-Length", [])
        if self.headers.get_all("Transfer-Encoding"):
            return self.reject_request(400, "Invalid content length.")
        if len(lengths) > 1 or (lengths and not re.fullmatch(r"[0-9]+", lengths[0])):
            return self.reject_request(400, "Invalid content length.")
        if not lengths and self.command == "POST":
            return self.reject_request(400, "Invalid content length.")
        digits = lengths[0].lstrip("0") if lengths else ""
        if len(digits) > len(str(MAX_BODY_BYTES)) or (digits and int(digits) > MAX_BODY_BYTES):
            return self.reject_request(413, "Request too large.")
        length = int(digits or "0")
        self.request_input.deadline = monotonic() + BODY_SECONDS
        try:
            self.request_body = self.rfile.read(length)
        except TimeoutError:
            return self.reject_request(408, "Request timed out.")
        if len(self.request_body) != length:
            return self.reject_request(400, "Incomplete request body.")
        self.connection.settimeout(WRITE_SECONDS)
        return True

    def reject_request(self, status, message):
        self.connection.settimeout(WRITE_SECONDS)
        self.request_error(status, message)
        return False

    def request_error(self, status, message):
        self.send_error(status, message)


class LimitedHTTPServer(ThreadingHTTPServer):
    """Starts a worker only when a slot is available; excess connections receive 503."""

    request_queue_size = 32

    def __init__(self, *args, max_requests=32, max_per_client=8, rate=4, burst=80, **kwargs):
        self.request_slots = threading.BoundedSemaphore(max_requests)
        self.trusted_proxies = trusted_proxies()
        self.client_limits = ClientLimits(max_per_client, rate, burst) if max_per_client else None
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.request_slots.acquire(blocking=False):
            try:
                request.settimeout(0.1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nConnection: close\r\n"
                                b"Content-Length: 0\r\nRetry-After: 1\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.request_slots.release()
