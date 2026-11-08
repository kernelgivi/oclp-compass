from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest

from compass.cli import main
from compass.engine import recommend
from compass.hardware import DEMO
from compass.planning import build_plan, compare, markdown_report
from compass.scenarios import simulate
from compass.schema import load_json, source_url, strict_json_loads

TODAY = date(2026, 11, 8)


class PlanningTests(unittest.TestCase):
    def setUp(self):
        self.ranking = recommend(DEMO, today=TODAY)

    def test_prerelease_plan_does_not_include_installation_steps(self):
        plan = build_plan(self.ranking, 26)
        self.assertTrue(plan["blocked"])
        self.assertEqual([p["id"] for p in plan["phases"]], ["prepare"])
        self.assertNotEqual(plan["state"], "checklist_complete")

    def test_unconfirmed_plan_requires_four_human_reviews(self):
        plan = build_plan(self.ranking, 15)
        self.assertEqual(plan["outstanding"], 4)
        self.assertEqual(plan["state"], "needs_review")

    def test_confirmations_do_not_unblock_excluded_target(self):
        confirmed = dict.fromkeys(("backup", "identity", "apps", "recovery"), True)
        plan = build_plan(self.ranking, 26, confirmed)
        self.assertTrue(plan["blocked"])
        self.assertNotEqual(plan["state"], "checklist_complete")

    def test_complete_is_labeled_as_planning_not_installation_readiness(self):
        confirmed = dict.fromkeys(("backup", "identity", "apps", "recovery"), True)
        plan = build_plan(self.ranking, 15, confirmed)
        self.assertEqual(plan["state"], "checklist_complete")
        self.assertEqual(plan["label"], "Planning checklist complete")
        self.assertIn("not permission", plan["disclaimer"])

    def test_low_and_unknown_free_space_need_review(self):
        for free in (None, 20):
            ranking = recommend(replace(DEMO, free_gb=free), today=TODAY)
            plan = build_plan(ranking, 15)
            check = next(c for c in plan["checks"] if c["id"] == "space")
            self.assertEqual(check["status"], "review")

    def test_invalid_confirmations_rejected(self):
        for confirmations in ({"backup": "yes"}, {"unknown": True}, [True]):
            with self.assertRaises(ValueError):
                build_plan(self.ranking, 15, confirmations)

    def test_downgrade_requires_explicit_caution(self):
        plan = build_plan(self.ranking, 12)
        self.assertEqual(plan["direction"], "downgrade")
        self.assertTrue(
            any("in-place downgrade" in caution for caution in plan["cautions"])
        )

    def test_same_major_does_not_imply_reinstall_needed(self):
        plan = build_plan(self.ranking, 15)
        self.assertEqual(plan["direction"], "same_major")
        self.assertTrue(
            any(
                "not automatically beneficial" in caution
                for caution in plan["cautions"]
            )
        )

    def test_native_and_oclp_paths_have_distinct_instructions(self):
        native = build_plan(self.ranking, 12)
        patched = build_plan(self.ranking, 15)
        self.assertIn("Apple's", native["phases"][1]["steps"][0])
        self.assertIn("Dortania", patched["phases"][1]["steps"][0])

    def test_unknown_target_rejected(self):
        for target in (True, 16, "15"):
            with self.assertRaises(ValueError):
                build_plan(self.ranking, target)

    def test_comparison_reports_signed_preference_deltas(self):
        comparison = compare(self.ranking, 12, 15)
        for metric in comparison["metrics"]:
            self.assertAlmostEqual(
                metric["delta"], metric["right"] - metric["left"], places=2
            )
        self.assertEqual(comparison["preferred"], 15)
        self.assertIn("not percentages", comparison["note"])

    def test_excluded_option_cannot_win_a_pairwise_comparison(self):
        result = compare(self.ranking, 11, 26)
        self.assertEqual(result["preferred"], 11)
        constrained = recommend(DEMO, min_os=26, today=TODAY)
        self.assertIsNone(compare(constrained, 15, 26)["preferred"])

    def test_comparing_identical_versions_is_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.ranking, 15, 15)

    def test_markdown_escapes_untrusted_app_names_and_notes(self):
        hardware = replace(
            DEMO, notes=("<script>alert(1)</script> [click](https://evil.example)",)
        )
        report = markdown_report(
            recommend(hardware, today=TODAY), build_plan(self.ranking, 15)
        )
        self.assertNotIn("<script>", report)
        self.assertNotIn("[click](https://evil.example)", report)
        self.assertIn("## Plan", report)
        self.assertIn("| Sequoia |", report)


class ScenarioTests(unittest.TestCase):
    def test_simulation_is_non_mutating(self):
        hw = replace(DEMO, ram_gb=4, storage="hdd")
        baseline = recommend(hw, today=TODAY)
        before = json.dumps(baseline, sort_keys=True)
        result = simulate(hw, baseline, ram_gb=16, storage="ssd", today=TODAY)
        self.assertEqual(hw.ram_gb, 4)
        self.assertEqual(hw.storage, "hdd")
        self.assertEqual(json.dumps(baseline, sort_keys=True), before)
        self.assertTrue(all(change["delta"] >= 0 for change in result["changes"]))
        self.assertIn("soldered", result["note"])

    def test_simulation_can_change_eligibility_but_never_prerelease_policy(self):
        hw = replace(DEMO, ram_gb=2)
        baseline = recommend(hw, today=TODAY)
        result = simulate(hw, baseline, ram_gb=8, today=TODAY)
        sequoia = next(c for c in result["changes"] if c["major"] == 15)
        tahoe = next(c for c in result["changes"] if c["major"] == 26)
        self.assertFalse(sequoia["eligible_before"])
        self.assertTrue(sequoia["eligible_after"])
        self.assertFalse(tahoe["eligible_after"])

    def test_simulation_rejects_invalid_hardware(self):
        baseline = recommend(DEMO, today=TODAY)
        with self.assertRaises(ValueError):
            simulate(DEMO, baseline, ram_gb=0, today=TODAY)


class SerializationTests(unittest.TestCase):
    def test_ambiguous_and_nonstandard_json_rejected(self):
        for raw in ('{"model":1,"model":2}', '{"ram_gb":NaN}', '{"ram_gb":Infinity}'):
            with self.assertRaises(ValueError):
                strict_json_loads(raw)

    def test_local_json_files_use_strict_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):
                load_json(path)

    def test_urls_cannot_break_out_of_markdown_autolinks(self):
        for url in (
            "https://reddit.com/a>b",
            "https://reddit.com/a b",
            "https://reddit.com/a\\b",
        ):
            with self.assertRaises(ValueError):
                source_url(url)


class CLITests(unittest.TestCase):
    def run_cli(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            status = main(args)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_compare_json(self):
        status, output, _ = self.run_cli(
            ["compare", "--demo", "--left", "12", "--right", "15", "--json"]
        )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output)["right"]["name"], "Sequoia")

    def test_blocked_plan_exit_code(self):
        status, output, _ = self.run_cli(["plan", "--demo", "--target", "26", "--json"])
        self.assertEqual(status, 3)
        self.assertTrue(json.loads(output)["blocked"])

    def test_markdown_export(self):
        status, output, _ = self.run_cli(
            ["recommend", "--demo", "--format", "markdown"]
        )
        self.assertEqual(status, 0)
        self.assertTrue(output.startswith("# OCLP Compass analysis"))

    def test_simulate_needs_a_configuration(self):
        status, _, error = self.run_cli(["simulate", "--demo"])
        self.assertEqual(status, 2)
        self.assertIn("needs --ram or --drive", error)

    def test_simulation_json(self):
        status, output, _ = self.run_cli(
            ["simulate", "--demo", "--ram", "8", "--drive", "hdd", "--json"]
        )
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output)["proposed"]["storage"], "hdd")
