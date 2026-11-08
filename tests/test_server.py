import http.client
import json
from threading import Thread
import unittest
from compass.hardware import DEMO, DetectionError, detect, parse_displays
from compass.server import make_server
import plistlib
from unittest.mock import patch


class HTTPFixture:
    @classmethod
    def setUpClass(cls):
        cls.server, cls.url = make_server(DEMO)
        cls.token = cls.url.split("#")[1]
        cls.origin = cls.url.split("/#")[0]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, path="/api/recommend", body=None, headers=None, method="POST"):
        c = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        h = {
            "Origin": self.origin,
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json",
        }
        h.update(headers or {})
        c.request(method, path, json.dumps(body if body is not None else {}), h)
        r = c.getresponse()
        raw = r.read()
        status = r.status
        response_headers = dict(r.getheaders())
        c.close()
        return status, raw, response_headers


class ServerTests(HTTPFixture, unittest.TestCase):
    def test_authenticated_ranking(self):
        status, raw, _ = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["hardware"]["model"], "MacBookPro13,3")

    def test_missing_token_rejected(self):
        self.assertEqual(self.request(headers={"Authorization": ""})[0], 401)

    def test_cross_origin_rejected(self):
        self.assertEqual(
            self.request(headers={"Origin": "https://evil.example"})[0], 403
        )

    def test_dns_rebinding_host_rejected(self):
        self.assertEqual(self.request(headers={"Host": "evil.example"})[0], 403)

    def test_get_does_not_disclose_hardware(self):
        self.assertEqual(self.request(method="GET", path="/api/session")[0], 404)

    def test_no_arbitrary_file_serving(self):
        for path in (
            "/../data/reports.json",
            "/compass/hardware.py",
            "/%2e%2e/etc/passwd",
        ):
            self.assertEqual(self.request(method="GET", path=path)[0], 404)

    def test_security_headers_and_no_embedded_secrets(self):
        status, body, headers = self.request(method="GET", path="/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn(self.token.encode(), body)
        self.assertNotIn(b"MacBookPro13,3", body)

    def test_oversize_payload_rejected(self):
        self.assertEqual(self.request(body={"x": "a" * 17000})[0], 413)

    def test_unknown_fields_rejected(self):
        self.assertEqual(self.request(body={"command": "anything"})[0], 400)

    def test_invalid_profile_rejected(self):
        self.assertEqual(
            self.request(body={"hardware": {"model": "MacBookPro13,3", "ram_gb": -5}})[
                0
            ],
            400,
        )

    def test_wrong_content_type_rejected(self):
        self.assertEqual(self.request(headers={"Content-Type": "text/plain"})[0], 400)

    def test_simulation_uses_same_engine(self):
        from compass.engine import recommend
        from dataclasses import replace

        hw = replace(DEMO, ram_gb=4)
        status, body, _ = self.request(
            body={"hardware": hw.to_dict(), "priority": "apps"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), recommend(hw, priority="apps"))


class HardwareTests(unittest.TestCase):
    def test_non_macos_fails_explicitly(self):
        with patch(
            "compass.hardware.platform.system", return_value="Linux"
        ), self.assertRaises(DetectionError):
            detect()

    def test_display_parser_retains_only_gpu_names(self):
        raw = plistlib.dumps(
            [{"_items": [{"sppci_model": "Intel HD Graphics 530", "serial": "secret"}]}]
        )
        self.assertEqual(parse_displays(raw), ("Intel HD Graphics 530",))

    def test_probe_fixed_arguments_and_private_projection(self):
        def probe(args):
            mapping = {
                "hw.model": b"MacBookPro13,3",
                "hw.memsize": str(16 * 2**30).encode(),
                "machdep.cpu.brand_string": b"Intel Core i7",
                "hw.physicalcpu": b"4",
                "machdep.cpu.leaf7_features": b"AVX2",
            }
            if args[0].endswith("sysctl"):
                return mapping[args[-1]]
            if args[0].endswith("system_profiler"):
                return plistlib.dumps(
                    [{"_items": [{"sppci_model": "Intel HD 530", "serial": "secret"}]}]
                )
            return plistlib.dumps(
                {
                    "SolidState": True,
                    "DeviceIdentifier": "private",
                    "VolumeUUID": "secret",
                }
            )

        with patch("compass.hardware.platform.system", return_value="Darwin"), patch(
            "compass.hardware.platform.machine", return_value="x86_64"
        ), patch("compass.hardware.run", side_effect=probe):
            hw = detect()
        self.assertEqual(hw.ram_gb, 16)
        self.assertTrue(hw.avx2)
        self.assertEqual(hw.storage, "ssd")
        self.assertNotIn("secret", json.dumps(hw.to_dict()))


class WorkbenchAPITests(HTTPFixture, unittest.TestCase):
    def test_compare_api(self):
        status, body, _ = self.request(
            path="/api/compare", body={"left": 12, "right": 15}
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["preferred"], 15)

    def test_blocked_plan_api(self):
        status, body, _ = self.request(path="/api/plan", body={"target": 26})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["blocked"])

    def test_plan_confirmation_validation(self):
        self.assertEqual(
            self.request(
                path="/api/plan",
                body={"target": 15, "confirmations": {"backup": "yes"}},
            )[0],
            400,
        )

    def test_scenario_api(self):
        status, body, _ = self.request(
            path="/api/simulate", body={"ram_gb": 4, "storage": "hdd"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["baseline"]["storage"], "ssd")
        self.assertEqual(json.loads(body)["proposed"]["storage"], "hdd")

    def test_report_api(self):
        status, body, _ = self.request(path="/api/report", body={"target": 15})
        self.assertEqual(status, 200)
        self.assertIn("## Plan", json.loads(body)["markdown"])

    def test_rescan_is_authenticated(self):
        self.assertEqual(
            self.request(path="/api/rescan", headers={"Authorization": ""})[0], 401
        )

    def test_rescan_unavailable_platform_returns_actionable_error(self):
        with patch(
            "compass.server.detect",
            side_effect=DetectionError("Automatic detection requires macOS"),
        ):
            status, body, _ = self.request(path="/api/rescan")
        self.assertEqual(status, 409)
        self.assertIn("requires macOS", json.loads(body)["error"])

    def test_session_has_honest_corpus_metadata(self):
        status, body, _ = self.request(path="/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(body)["evidence"], {"source": "bundled", "total": 2, "models": 2}
        )

    def test_sensitive_routes_are_not_get_endpoints(self):
        for route in (
            "/api/plan",
            "/api/simulate",
            "/api/compare",
            "/api/report",
            "/api/rescan",
        ):
            self.assertEqual(self.request(path=route, method="GET")[0], 404)
