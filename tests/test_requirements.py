from dataclasses import replace
from datetime import date
import unittest
from compass.engine import recommend
from compass.hardware import DEMO
from compass.requirements import validate_requirements


class AppRequirementsTests(unittest.TestCase):
    app = {"name": "Required editor", "min_os": 14, "avx2": False, "metal": False}

    def test_os_requirement_filters(self):
        r = recommend(DEMO, requirements=[self.app], today=date(2026, 11, 8))
        self.assertTrue(
            all(not c["eligible"] for c in r["candidates"] if c["major"] < 14)
        )
        self.assertIn(r["recommendation"], (14, 15))

    def test_avx2_requirement_cannot_be_satisfied_by_newer_os(self):
        for avx2 in (False, None):
            r = recommend(
                replace(DEMO, avx2=avx2), requirements=[{**self.app, "avx2": True}]
            )
            self.assertIsNone(r["recommendation"])

    def test_non_metal_cannot_satisfy_metal_requirement(self):
        r = recommend(
            replace(DEMO, model="MacBookPro8,1"),
            requirements=[{**self.app, "metal": True}],
        )
        self.assertIsNone(r["recommendation"])

    def test_invalid_input_rejected(self):
        for value in (
            [{**self.app, "avx2": "yes"}],
            [self.app, self.app],
            [{**self.app, "min_os": 16}],
        ):
            with self.assertRaises(ValueError):
                validate_requirements(value)
