"""Bounded HTTP connections and absolute request-body deadlines for local services."""
from __future__ import annotations

import socket
import threading
from http.server import ThreadingHTTPServer


def read_body(handler, maximum, *, timeout):
    lengths = handler.headers.get_all("Content-Length") or []
    if len(lengths) != 1 or handler.headers.get("Transfer-Encoding"):
        raise ValueError("one Content-Length is required")
    if not lengths[0].isdigit() or not 0 < int(lengths[0]) <= maximum:
        raise ValueError("request body exceeds its limit")
    length = int(lengths[0])

    def interrupt():
        try:
            handler.connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    timer = threading.Timer(timeout, interrupt)
    timer.daemon = True
    timer.start()
    try:
        data = handler.rfile.read(length)
        if len(data) != length:
            raise ValueError("incomplete request body")
        return data
    except OSError:
        raise ValueError("request body deadline exceeded") from None
    finally:
        timer.cancel()


class BoundedHTTPServer(ThreadingHTTPServer):
    def __init__(self, address, handler):
        self.slots = threading.BoundedSemaphore(16)
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        def interrupt():
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        timer = threading.Timer(60, interrupt)
        timer.daemon = True
        timer.start()
        try:
            super().process_request_thread(request, client_address)
        finally:
            timer.cancel()
            self.slots.release()
