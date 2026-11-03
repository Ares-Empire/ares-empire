"""Request limits with in-memory input, a controlled clock, and bounded local workers."""

import io
from email.message import Message
import threading
import time
import unittest
from unittest.mock import Mock, patch

import empire_http
from push import server as push
from webauth import server as hub


class Input(io.BytesIO):
    def __init__(self, sock, data, chunks=None):
        super().__init__(data)
        self.sock = sock
        self.chunks = iter(chunks or [])
        self.reads = 0

    def read1(self, size):
        self.reads += 1
        limit, delay = next(self.chunks, (size, 0))
        if delay > self.sock.timeout:
            self.sock.now += self.sock.timeout
            raise TimeoutError()
        self.sock.now += delay
        return super().read1(min(size, limit))


class Socket:
    def __init__(self, data, chunks=None):
        self.now = 0
        self.timeout = 0
        self.input = Input(self, data, chunks)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def settimeout(self, seconds):
        self.timeout = seconds

    def sendall(self, data):
        self.output.write(data)


class RequestLimitTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(hub.Handler, "log_message"))
        self.enterContext(patch.object(push.Handler, "log_message"))
        self.service = Mock()
        self.service.health.return_value = {"ok": True}
        self.service.send.return_value = {"sent": 0}
        self.httpd = Mock(service=self.service)

    def handlers(self):
        return ((hub.Handler, "/forgot"), (hub.Handler, "/api/empire/request"),
                (push.PublicHandler, "/api/push/devices"), (push.InternalHandler, "/send"))

    def request(self, handler, path, headers=b"", body=b"", chunks=None, method="POST"):
        data = f"{method} {path} HTTP/1.1\r\n".encode() + headers + b"\r\n" + body
        sock = Socket(data, chunks)
        with patch.object(empire_http, "monotonic", side_effect=lambda: sock.now):
            handler(sock, ("127.0.0.1", 1234), self.httpd)
        output = sock.output.getvalue()
        status = int(output.split(b" ", 2)[1]) if output else None
        return status, sock

    def test_oversize_length_is_refused_before_any_body_read(self):
        for handler, path in self.handlers():
            for length in ("10001", "9" * 5000):
                with self.subTest(handler=handler, path=path, length=length[:8]):
                    headers = f"Content-Length: {length}\r\n".encode()
                    head_length = len(f"POST {path} HTTP/1.1\r\n".encode() + headers + b"\r\n")
                    status, sock = self.request(handler, path, headers, chunks=[(head_length, 0)])
                    self.assertEqual(status, 413)
                    self.assertEqual(sock.input.reads, 1)
        self.assertEqual(self.service.mock_calls, [])

    def test_missing_malformed_duplicate_and_transfer_lengths_are_400(self):
        headers = (b"", b"Content-Length: -1\r\n", b"Content-Length: +2\r\n",
                   b"Content-Length: nope\r\n", b"Content-Length: 2, 2\r\n",
                   b"Content-Length: 2\r\nContent-Length: 2\r\n",
                   b"Transfer-Encoding: chunked\r\n", b"Transfer-Encoding: identity\r\nContent-Length: 2\r\n")
        for handler, path in self.handlers():
            for header in headers:
                with self.subTest(handler=handler, path=path, header=header):
                    self.assertEqual(self.request(handler, path, header)[0], 400)
        self.assertEqual(self.service.mock_calls, [])

    def test_short_body_is_400_and_does_not_run_route(self):
        for handler, path in self.handlers():
            with self.subTest(handler=handler, path=path):
                self.assertEqual(self.request(handler, path, b"Content-Length: 20\r\n", b"{}")[0], 400)
        self.assertEqual(self.service.mock_calls, [])

    def test_body_deadline_is_absolute_even_with_regular_progress(self):
        for handler, path in self.handlers():
            with self.subTest(handler=handler, path=path):
                headers = b"Content-Length: 20\r\nAccept-Language: de\r\n"
                head_length = len(f"POST {path} HTTP/1.1\r\n".encode() + headers + b"\r\n")
                status, sock = self.request(handler, path, headers, b"x" * 20,
                                            [(head_length, 0)] + [(1, 1)] * 20)
                self.assertEqual(status, 408)
                self.assertEqual(sock.now, empire_http.BODY_SECONDS)
                if handler is not hub.Handler or path.startswith("/api/"):
                    self.assertIn(b"Content-Language: de", sock.output.getvalue())
        self.assertEqual(self.service.mock_calls, [])

    def test_header_deadline_is_absolute_with_regular_progress(self):
        for handler, path in self.handlers():
            with self.subTest(handler=handler):
                status, sock = self.request(handler, path, b"Content-Length: 2\r\n", b"{}", [(1, 1)] * 100)
                self.assertIsNone(status)  # closes an incomplete request line
                self.assertEqual(sock.now, empire_http.HEADER_SECONDS)

    def test_partial_headers_also_close_at_the_deadline(self):
        for handler, path in self.handlers():
            with self.subTest(handler=handler):
                line_length = len(f"POST {path} HTTP/1.1\r\n".encode())
                status, sock = self.request(handler, path, b"Content-Length: 2\r\n", b"{}",
                                            [(line_length, 0)] + [(1, 1)] * 100)
                self.assertIsNone(status)
                self.assertEqual(sock.now, empire_http.HEADER_SECONDS)

    def test_exact_body_limit_and_separate_header_body_deadlines(self):
        body = b"{}" + b" " * (empire_http.MAX_BODY_BYTES - 2)
        for handler, path in ((hub.Handler, "/forgot"), (push.PublicHandler, "/api/push/devices"),
                              (push.InternalHandler, "/send")):
            with self.subTest(handler=handler):
                headers = f"Content-Length: {len(body)}\r\n".encode()
                head_length = len(f"POST {path} HTTP/1.1\r\n".encode() + headers + b"\r\n")
                status, sock = self.request(handler, path, headers, body, [(head_length, 4), (len(body), 4)])
                self.assertIn(status, (200, 204))
                self.assertEqual(sock.now, 8)

    def test_a_request_always_closes_including_an_unread_extra_body(self):
        status, sock = self.request(push.InternalHandler, "/health", b"Content-Length: 0\r\n",
                                    b"GET /health HTTP/1.1\r\n\r\n", method="GET")
        self.assertEqual(status, 200)
        self.assertEqual(self.service.health.call_count, 1)


class WorkerLimitTests(unittest.TestCase):
    def make_server(self, handler, limit=1):
        httpd = empire_http.LimitedHTTPServer(("127.0.0.1", 0), handler,
                                              max_requests=limit, bind_and_activate=False)
        httpd.daemon_threads = False
        self.addCleanup(httpd.server_close)
        return httpd

    def test_overload_is_503_without_starting_another_worker_and_slot_recovers(self):
        entered = threading.Event()
        finish = threading.Event()
        self.addCleanup(finish.set)

        def handler(*args):
            entered.set()
            finish.wait(2)

        httpd = self.make_server(handler)
        first, excess = Mock(), Mock()
        httpd.process_request(first, ("127.0.0.1", 1))
        self.assertTrue(entered.wait(1))
        httpd.process_request(excess, ("127.0.0.1", 2))
        self.assertTrue(excess.sendall.call_args.args[0].startswith(b"HTTP/1.0 503"))
        self.assertEqual(excess.settimeout.call_args.args, (0.1,))
        excess.close.assert_called_once()
        finish.set()
        httpd._threads.join()
        self.assertTrue(httpd.request_slots.acquire(blocking=False))

    def test_failed_worker_releases_slot(self):
        httpd = self.make_server(Mock(side_effect=ValueError("failed")))
        self.assertTrue(httpd.request_slots.acquire(blocking=False))
        with patch.object(httpd, "handle_error"):
            httpd.process_request_thread(Mock(), ("127.0.0.1", 1))
        self.assertTrue(httpd.request_slots.acquire(blocking=False))

    def test_failed_thread_start_releases_slot(self):
        httpd = self.make_server(Mock())
        httpd.daemon_threads = True
        with patch.object(threading.Thread, "start", side_effect=RuntimeError("failed")):
            with self.assertRaises(RuntimeError):
                httpd.process_request(Mock(), ("127.0.0.1", 1))
        self.assertTrue(httpd.request_slots.acquire(blocking=False))

    def test_defaults_and_push_listeners_have_separate_pools(self):
        httpd = self.make_server(Mock(), 32)
        self.assertEqual(httpd.request_queue_size, 32)
        with patch.object(push, "LimitedHTTPServer") as server_type:
            push.serve(push.PublicHandler, 0, Mock())
            self.assertEqual(server_type.call_args.kwargs,
                             {"max_requests": 16, "max_per_client": 4, "rate": 1, "burst": 20})

    def test_one_full_pool_does_not_use_another_listeners_slots(self):
        public = self.make_server(Mock())
        internal = self.make_server(Mock())
        self.assertTrue(public.request_slots.acquire(blocking=False))
        self.assertFalse(public.request_slots.acquire(blocking=False))
        self.assertTrue(internal.request_slots.acquire(blocking=False))

    def test_one_forwarded_client_leaves_workers_for_another_client(self):
        self.assert_forwarded_client_isolation(hub.Handler, "/forgot", 32, 8, 200)

    def test_one_forwarded_client_leaves_push_workers_for_another_client(self):
        self.assert_forwarded_client_isolation(push.PublicHandler, "/api/push/devices", 16, 4, 204)

    def assert_forwarded_client_isolation(self, handler_type, path, workers, client_limit, expected):
        release = threading.Event()
        sockets = []
        httpd = self.make_server(handler_type, workers)
        httpd.client_limits = empire_http.ClientLimits(concurrent=client_limit)
        httpd.service = Mock()

        class BodyInput(io.BytesIO):
            def read1(self, size):
                if self.tell() < self.header_length:
                    return super().read1(min(size, self.header_length - self.tell()))
                self.waiting.set()
                release.wait(3)
                return super().read1(size)

        def request(ip, incomplete):
            body = b"{}" if incomplete or handler_type is push.PublicHandler else b""
            head = (f"POST {path} HTTP/1.0\r\nX-Forwarded-For: {ip}\r\n"
                    f"Content-Length: {len(body)}\r\n\r\n").encode()
            sock = Socket(head + body)
            sock.shutdown = lambda *args: None
            sock.close = lambda: None
            if incomplete:
                sock.input = BodyInput(head + body)
                sock.input.header_length = len(head)
                sock.input.waiting = threading.Event()
            sockets.append(sock)
            httpd.process_request(sock, ("127.0.0.1", 1234))
            return sock

        with patch.object(handler_type, "log_message"):
            try:
                for _ in range(workers):
                    request("192.0.2.55", True)
                deadline = time.monotonic() + 1
                while not all(sock.input.waiting.is_set() or sock.output.getvalue() for sock in sockets):
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(0.005)
                legitimate = request("192.0.2.56", False)
                deadline = time.monotonic() + 1
                while not legitimate.output.getvalue() and time.monotonic() < deadline:
                    time.sleep(0.005)
                self.assertTrue(legitimate.output.getvalue().startswith(f"HTTP/1.0 {expected}".encode()))
                self.assertTrue(any(sock.output.getvalue().startswith(b"HTTP/1.0 503") for sock in sockets[:-1]))
            finally:
                release.set()
                httpd._threads.join()


class ClientLimitTests(unittest.TestCase):
    def test_forwarded_addresses_are_used_only_from_the_configured_proxy(self):
        for handler_type in (hub.Handler, push.PublicHandler):
            for peer, forwarded, expected in (
                ("127.0.0.1", "203.0.113.10, 192.0.2.55", "192.0.2.55"),
                ("192.0.2.8", "192.0.2.55", "192.0.2.8"),
                ("::ffff:192.0.2.8", "192.0.2.55", "192.0.2.8"),
                ("127.0.0.1", "not-an-address", "127.0.0.1"),
            ):
                with self.subTest(handler=handler_type, peer=peer):
                    handler = object.__new__(handler_type)
                    handler.client_address = (peer, 1234)
                    handler.server = object()
                    handler.headers = Message()
                    handler.headers["X-Forwarded-For"] = forwarded
                    with patch.dict("os.environ", {"AUTH_TRUSTED_PROXY": "127.0.0.1"}):
                        self.assertEqual(handler.request_client_ip(), expected)

    def test_concurrency_and_rate_limits_leave_other_clients_available(self):
        now = [0]
        limits = empire_http.ClientLimits(concurrent=2, rate=1, burst=3, clock=lambda: now[0])
        self.assertEqual(limits.acquire("first"), 0)
        self.assertEqual(limits.acquire("first"), 0)
        self.assertEqual(limits.acquire("first"), 503)
        self.assertEqual(limits.acquire("second"), 0)
        limits.release("first")
        self.assertEqual(limits.acquire("first"), 429)
        now[0] = 1
        self.assertEqual(limits.acquire("first"), 0)

    def test_rate_rejection_happens_before_the_body_is_read(self):
        httpd = empire_http.LimitedHTTPServer(("127.0.0.1", 0), push.PublicHandler,
                                              bind_and_activate=False, burst=1, rate=0)
        self.addCleanup(httpd.server_close)
        self.assertEqual(httpd.client_limits.acquire("192.0.2.55"), 0)
        httpd.client_limits.release("192.0.2.55")
        head = (b"POST /api/push/devices HTTP/1.0\r\nX-Forwarded-For: 192.0.2.55\r\n"
                b"Content-Length: 20\r\n\r\n")
        sock = Socket(head, [(len(head), 0)])
        with patch.object(push.Handler, "log_message"):
            push.PublicHandler(sock, ("127.0.0.1", 1234), httpd)
        self.assertTrue(sock.output.getvalue().startswith(b"HTTP/1.0 429"))
        self.assertEqual(sock.input.reads, 1)

    def test_client_bookkeeping_is_bounded_and_keeps_active_entries(self):
        limits = empire_http.ClientLimits()
        self.assertEqual(limits.acquire("active"), 0)
        for number in range(4100):
            key = str(number)
            self.assertEqual(limits.acquire(key), 0)
            limits.release(key)
        self.assertEqual(len(limits.clients), 4096)
        limits.release("active")


if __name__ == "__main__":
    unittest.main()
