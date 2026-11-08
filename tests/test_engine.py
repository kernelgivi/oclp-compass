from dataclasses import replace
from datetime import date
import unittest
from compass.engine import data, recommend
from compass.hardware import DEMO
from compass.schema import Hardware
from compass.evidence import summarize, validate_reports

TODAY = date(2026, 11, 8)


class EngineTests(unittest.TestCase):
    def result(self, **kwargs):
        return recommend(DEMO, today=TODAY, **kwargs)

    def test_unknown_model_abstains(self):
        r = recommend(replace(DEMO, model="MacPro5,1"), today=TODAY)
        self.assertEqual(r["status"], "unreviewed")
        self.assertIsNone(r["recommendation"])

    def test_apple_silicon_abstains_even_with_intel_identifier(self):
        self.assertEqual(
            recommend(replace(DEMO, arch="arm64"), today=TODAY)["status"],
            "apple_silicon",
        )

    def test_unknown_arch_abstains(self):
        self.assertIsNone(
            recommend(replace(DEMO, arch="unknown"), today=TODAY)["recommendation"]
        )

    def test_no_stable_os_meets_tahoe_minimum(self):
        self.assertIsNone(self.result(min_os=26)["recommendation"])

    def test_prerelease_never_recommended(self):
        for preset in ("apps", "balanced", "smoothness"):
            r = self.result(priority=preset)
            self.assertNotEqual(r["recommendation"], 26)
            self.assertFalse(
                next(c for c in r["candidates"] if c["major"] == 26)["eligible"]
            )

    def test_preferences_change_direction(self):
        self.assertEqual(self.result(priority="smoothness")["recommendation"], 11)
        self.assertEqual(self.result(priority="apps")["recommendation"], 15)

    def test_low_ram_excludes_sonoma_and_sequoia(self):
        r = recommend(replace(DEMO, ram_gb=2), today=TODAY)
        self.assertTrue(
            all(not c["eligible"] for c in r["candidates"] if c["major"] >= 14)
        )

    def test_app_minimum_is_hard_constraint(self):
        r = self.result(min_os=15)
        self.assertEqual(r["recommendation"], 15)
        self.assertTrue(
            all(not c["eligible"] for c in r["candidates"] if c["major"] < 15)
        )

    def test_catalog_uses_explicit_identifiers(self):
        for model in data("models"):
            r = recommend(replace(DEMO, model=model), today=TODAY)
            self.assertEqual(len(r["candidates"]), 6)
            for c in r["candidates"]:
                for key in ("score", "smoothness", "app_recency", "maintenance"):
                    self.assertTrue(0 <= c[key] <= 100)
                self.assertEqual(
                    c["route"] == "Native", c["major"] <= r["model"]["native_max"]
                )

    def test_storage_penalty_is_monotonic(self):
        def smooth(kind):
            return {
                c["major"]: c["smoothness"]
                for c in recommend(
                    replace(DEMO, storage=kind), reports=[], today=TODAY
                )["candidates"]
            }

        a, b = smooth("ssd"), smooth("hdd")
        self.assertTrue(all(a[k] >= b[k] for k in a))

    def test_stale_snapshot_visible(self):
        self.assertTrue(recommend(DEMO, today=date(2027, 5, 1))["stale"])

    def test_kepler_requires_monterey_patches(self):
        r = recommend(replace(DEMO, model="MacBookPro11,3"), today=TODAY)
        self.assertTrue(
            next(c for c in r["candidates"] if c["major"] == 12)["graphics_patches"]
        )

    def test_2014_imac_big_sur_is_native(self):
        r = recommend(replace(DEMO, model="iMac14,4"), today=TODAY)
        self.assertEqual(
            next(c for c in r["candidates"] if c["major"] == 11)["route"], "Native"
        )

    def test_invalid_priorities_and_requirements(self):
        for kwargs in ({"priority": "random"}, {"min_os": 16}, {"min_os": True}):
            with self.assertRaises(ValueError):
                self.result(**kwargs)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.report = dict(data("reports")[0])

    def test_seed_valid(self):
        self.assertEqual(len(validate_reports(data("reports"), TODAY)), 2)

    def test_duplicate_permalink_rejected(self):
        second = {
            **self.report,
            "id": "new",
            "url": self.report["url"].replace("www.reddit", "reddit").rstrip("/"),
        }
        with self.assertRaises(ValueError):
            validate_reports([self.report, second], TODAY)

    def test_future_dates_rejected(self):
        for key in ("reported_on", "reviewed_on"):
            with self.assertRaises(ValueError):
                validate_reports([{**self.report, key: "2099-01-01"}], TODAY)

    def test_dangerous_urls_rejected(self):
        for url in (
            "javascript:alert(1)",
            "https://reddit.com.evil.test/x",
            "http://reddit.com/x",
            "https://user@reddit.com/x",
            "https://reddit.com/x?token=x",
            "https://127.0.0.1/x",
            "https://reddit.com/a>b",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_reports([{**self.report, "url": url}], TODAY)

    def test_no_same_family_transfer(self):
        evidence = summarize(
            [self.report], replace(DEMO, model="MacBookPro13,2"), 15, TODAY
        )
        self.assertEqual(evidence["count"], 0)

    def test_repeated_author_does_not_inflate_weight(self):
        second = {**self.report, "id": "second", "url": "https://reddit.com/second"}
        evidence = summarize([self.report, second], DEMO, 15, TODAY)
        self.assertEqual(evidence["independent"], 1)

    def test_single_anecdote_has_small_effect(self):
        evidence = summarize([self.report], DEMO, 15, TODAY)
        self.assertGreater(evidence["adjustment"], 0)
        self.assertLess(evidence["adjustment"], 1)

    def test_conflict_is_visible(self):
        other = {
            **self.report,
            "id": "negative",
            "author": "independent",
            "sentiment": "negative",
            "url": "https://reddit.com/negative",
        }
        evidence = summarize([self.report, other], DEMO, 15, TODAY)
        self.assertTrue(evidence["conflicting"])
        self.assertEqual(evidence["adjustment"], 0)

    def test_complete_recent_reports_weigh_more(self):
        recent = {
            **self.report,
            "reported_on": "2026-11-01",
            "ram_gb": 16,
            "storage": "ssd",
        }
        a = summarize([recent], DEMO, 15, TODAY)
        b = summarize([self.report], DEMO, 15, TODAY)
        self.assertGreater(a["effective_sample"], b["effective_sample"])

    def test_untrusted_extra_fields_rejected(self):
        with self.assertRaises(ValueError):
            validate_reports([{**self.report, "execute": "rm"}], TODAY)

    def test_invalid_hardware_rejected(self):
        for patch in (
            {"ram_gb": float("nan")},
            {"ram_gb": True},
            {"model": "../../etc/passwd"},
            {"storage": "nvme"},
            {"avx2": "yes"},
        ):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                replace(DEMO, **patch)
