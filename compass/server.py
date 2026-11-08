"""Capability-authenticated, loopback-only UI; no file-write or patch endpoints."""

from __future__ import annotations
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import secrets
from threading import BoundedSemaphore
import webbrowser
from .engine import data, recommend
from .schema import Hardware, strict_json_loads
from .planning import build_plan, compare, markdown_report
from .scenarios import simulate
from .hardware import detect, DetectionError

ASSETS = {
    "/api.js": ("api.js", "application/javascript; charset=utf-8"),
    "/dom.js": ("dom.js", "application/javascript; charset=utf-8"),
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
MAX_BODY = 16_384


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, *args, **kwargs):
        self.slots = BoundedSemaphore(16)
        super().__init__(*args, **kwargs)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def get_request(self):
        sock, address = super().get_request()
        sock.settimeout(5)
        return sock, address


class Handler(BaseHTTPRequestHandler):
    server_version = "Compass"
    sys_version = ""

    def __init__(self, *args, hardware, token, reports, requirements, **kwargs):
        self.hardware, self.token, self.reports, self.requirements = (
            hardware,
            token,
            reports,
            requirements,
        )
        super().__init__(*args, **kwargs)

    def log_message(self, *_args):
        pass  # No request logging; capabilities must not enter logs.

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def respond(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        )
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def host_ok(self):
        return self.headers.get_all("Host") == [f"127.0.0.1:{self.server.server_port}"]

    def do_GET(self):
        if not self.host_ok():
            return self.respond(403, {"error": "Invalid Host"})
        asset = ASSETS.get(self.path)
        if not asset:
            return self.respond(404, {"error": "Not found"})
        filename, mime = asset
        return self.respond(
            200, files("compass").joinpath("web", filename).read_bytes(), mime
        )

    def do_POST(self):
        if not self.host_ok() or self.headers.get_all("Origin") != [self.origin]:
            return self.respond(403, {"error": "Origin rejected"})
        auth = self.headers.get_all("Authorization") or []
        if len(auth) != 1 or not secrets.compare_digest(
            auth[0].encode(), ("Bearer " + self.token).encode()
        ):
            return self.respond(
                401, {"error": "Session expired. Reopen the URL printed by Compass."}
            )
        if self.headers.get("Transfer-Encoding") or self.headers.get_all(
            "Content-Type"
        ) != ["application/json"]:
            return self.respond(400, {"error": "Expected JSON with a Content-Length"})
        lengths = self.headers.get_all("Content-Length") or []
        try:
            if len(lengths) != 1:
                raise ValueError("Missing or duplicate Content-Length")
            length = int(lengths[0])
            if not 0 < length <= MAX_BODY:
                return self.respond(413, {"error": "Request size rejected"})
            request = strict_json_loads(self.rfile.read(length))
            if not isinstance(request, dict):
                raise ValueError("Expected an object")
            if self.path == "/api/session":
                if request:
                    raise ValueError("Session request must be empty")
                corpus = data("reports") if self.reports is None else self.reports
                return self.respond(
                    200,
                    {
                        "hardware": self.hardware.to_dict(),
                        "models": data("models"),
                        "requirements": self.requirements or [],
                        "evidence": {
                            "source": "bundled" if self.reports is None else "imported",
                            "total": len(corpus),
                            "models": len({r["model"] for r in corpus}),
                        },
                    },
                )
            if self.path == "/api/rescan":
                if request:
                    raise ValueError("Rescan request must be empty")
                return self.respond(200, {"hardware": detect().to_dict()})
            fields = {
                "/api/recommend": set(),
                "/api/compare": {"left", "right"},
                "/api/plan": {"target", "confirmations"},
                "/api/simulate": {"ram_gb", "storage"},
                "/api/report": {"target", "confirmations"},
            }
            if self.path not in fields:
                return self.respond(404, {"error": "Not found"})
            common = {"hardware", "priority", "min_os", "requirements"}
            if set(request) - common - fields[self.path]:
                raise ValueError("Unknown request fields")
            hw = (
                Hardware.from_dict(request["hardware"])
                if "hardware" in request
                else self.hardware
            )
            ranking = recommend(
                hw,
                request.get("priority", "balanced"),
                request.get("min_os", 11),
                self.reports,
                requirements=request.get("requirements", self.requirements),
            )
            if self.path == "/api/recommend":
                response = ranking
            elif self.path == "/api/compare":
                response = compare(ranking, request["left"], request["right"])
            elif self.path == "/api/plan":
                response = build_plan(
                    ranking, request["target"], request.get("confirmations")
                )
            elif self.path == "/api/simulate":
                response = simulate(
                    hw,
                    ranking,
                    ram_gb=request.get("ram_gb"),
                    storage=request.get("storage"),
                    reports=self.reports,
                )
            else:
                plan = (
                    build_plan(ranking, request["target"], request.get("confirmations"))
                    if "target" in request
                    else None
                )
                response = {"markdown": markdown_report(ranking, plan)}
            return self.respond(200, response)
        except DetectionError as exc:
            return self.respond(409, {"error": str(exc)[:300]})
        except (ValueError, TypeError, KeyError) as exc:
            return self.respond(400, {"error": str(exc)[:300]})


def make_server(hardware, reports=None, port=0, requirements=None):
    token = secrets.token_urlsafe(32)
    server = Server(
        ("127.0.0.1", port),
        partial(
            Handler,
            hardware=hardware,
            token=token,
            reports=reports,
            requirements=requirements,
        ),
    )
    return server, f"http://127.0.0.1:{server.server_port}/#{token}"


def serve(hardware, reports=None, port=0, open_browser=True, requirements=None):
    server, url = make_server(hardware, reports, port, requirements)
    print(
        "OCLP Compass · local session. Keep this URL private. Ctrl-C to stop.\n" + url,
        flush=True,
    )
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
