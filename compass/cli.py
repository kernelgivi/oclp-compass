"""Terminal interface, sharing the GUI's exact detection and ranking engine."""

from __future__ import annotations
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from . import __version__
from .engine import PROFILES, data, recommend
from .evidence import validate_reports
from .hardware import DEMO, DetectionError, detect
from .planning import build_plan, compare, markdown_report
from .scenarios import simulate
from .requirements import validate_requirements
from .schema import Hardware, load_json


def parser():
    p = argparse.ArgumentParser(
        prog="oclp-compass",
        description="Evidence-aware macOS upgrade planning. Read-only. No administrator access required.",
    )
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("models", help="List reviewed model policies")
    validate = sub.add_parser(
        "validate-evidence",
        help="Validate a community report JSON file without fetching links",
    )
    validate.add_argument("file", type=Path)
    for name in ("detect", "recommend", "gui", "compare", "plan", "simulate"):
        cmd = sub.add_parser(name)
        source = cmd.add_mutually_exclusive_group()
        source.add_argument(
            "--demo",
            action="store_true",
            help="Use a clearly labeled 2016 MacBook Pro example",
        )
        source.add_argument(
            "--profile", type=Path, help="Use an exported hardware profile"
        )
        cmd.add_argument(
            "--storage",
            choices=("ssd", "hdd", "fusion", "unknown"),
            help="Explicit boot-drive correction",
        )
        if name != "gui":
            cmd.add_argument(
                "--json", action="store_true", help="Machine-readable output"
            )
        if name != "detect":
            cmd.add_argument(
                "--requirements",
                type=Path,
                help="Essential app minimum OS / AVX2 / Metal requirements JSON",
            )
            cmd.add_argument(
                "--reports",
                type=Path,
                help="Replace the seed evidence corpus with validated local reports",
            )
        if name in {"recommend", "compare", "plan", "simulate"}:
            cmd.add_argument("--priority", choices=PROFILES, default="balanced")
            cmd.add_argument(
                "--min-os",
                type=int,
                choices=(11, 12, 13, 14, 15, 26),
                default=11,
                help="Minimum OS required by your apps; enter after checking vendor requirements",
            )
        if name == "recommend":
            cmd.add_argument(
                "--format", choices=("text", "json", "markdown"), default="text"
            )
        if name == "compare":
            cmd.add_argument("--left", type=int, required=True)
            cmd.add_argument("--right", type=int, required=True)
        if name == "plan":
            cmd.add_argument("--target", type=int, required=True)
        if name == "simulate":
            cmd.add_argument(
                "--ram",
                type=float,
                help="Hypothetical RAM in GiB; does not imply upgradeability",
            )
            cmd.add_argument("--drive", choices=("ssd", "hdd", "fusion", "unknown"))
        if name == "gui":
            cmd.add_argument("--no-browser", action="store_true")
            cmd.add_argument(
                "--port",
                type=int,
                default=0,
                help="Loopback port; 0 selects a free port",
            )
    return p


def terminal(result):
    hw = result["hardware"]
    out = [
        f"OCLP COMPASS  /  {hw['model']}  /  {hw['origin'].upper()}",
        f"{hw['ram_gb']:g} GiB RAM · {hw['storage'].upper()} · macOS {hw['current_os']}",
        f"Policy {result['policy']['reviewed']} · {result['priority']} priority",
        "",
    ]
    if result["recommendation"]:
        chosen = next(
            c for c in result["candidates"] if c["major"] == result["recommendation"]
        )
        out.append(f"Provisional best fit: macOS {chosen['name']} ({chosen['route']})")
    else:
        out.append(
            "No installation recommendation under the current policy / constraints."
        )
    out += ["", "OS           Route   Fit   Smooth  Apps  Care  Independent reports"]
    for c in result["candidates"]:
        out.append(
            f"{c['name']:<12} {c['route']:<7} {c['score']:>4.1f}  {c['smoothness']:>5.1f}  {c['app_recency']:>4}  {c['maintenance']:>4}  {c['evidence']['independent']:>3}  {'eligible' if c['eligible'] else 'excluded'}"
        )
        for reason in c["blocks"] + c["reasons"]:
            out.append("  - " + reason)
        for r in c["evidence"]["reports"]:
            out.append(f"  [{r['sentiment']}] {r['summary']}\n    {r['url']}")
    out += [
        "",
        "Scores are preference heuristics, not benchmarks; Apps is OS recency, not verified app support.",
    ]
    out += ["! " + w for w in result["warnings"]]
    out += ["", "Before installation:"] + ["  " + c for c in result["checklist"]]
    return "\n".join(out)


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "models":
            for model, spec in data("models").items():
                print(f"{model:<20} {spec['name']}")
            return 0
        if args.command == "validate-evidence":
            reports = validate_reports(load_json(args.file))
            print(
                f"Valid: {len(reports)} reports. Structural validation does not verify authenticity."
            )
            return 0
        hw = (
            DEMO
            if args.demo
            else (
                Hardware.from_dict(load_json(args.profile))
                if args.profile
                else detect()
            )
        )
        if args.storage:
            hw = replace(
                hw,
                storage=args.storage,
                notes=(*hw.notes, "Boot-drive type explicitly overridden by the user."),
            )
        if args.command == "detect":
            print(
                json.dumps(hw.to_dict(), indent=2)
                if args.json
                else f"{hw.model} · {hw.ram_gb:g} GiB · {hw.storage}\n"
                + "\n".join(hw.notes)
            )
            return 0
        reports = validate_reports(load_json(args.reports)) if args.reports else None
        requirements = (
            validate_requirements(load_json(args.requirements))
            if args.requirements
            else []
        )
        if args.command == "gui":
            if not 0 <= args.port <= 65535:
                raise ValueError("Port must be between 0 and 65535")
            from .server import serve

            serve(hw, reports, args.port, not args.no_browser, requirements)
            return 0
        result = recommend(
            hw, args.priority, args.min_os, reports, requirements=requirements
        )
        if args.command == "compare":
            comparison = compare(result, args.left, args.right)
            if args.json:
                print(json.dumps(comparison, indent=2, allow_nan=False))
            else:
                print(f"{comparison['left']['name']} → {comparison['right']['name']}")
                for metric in comparison["metrics"]:
                    print(
                        f"{metric['label']}: {metric['left']} → {metric['right']} ({metric['delta']:+g} points)"
                    )
                print(comparison["note"])
                print("\n".join(comparison["differences"]))
            return 0 if comparison["preferred"] is not None else 3
        if args.command == "plan":
            plan = build_plan(result, args.target)
            if args.json:
                print(json.dumps(plan, indent=2, allow_nan=False))
            else:
                print(f"macOS {plan['name']} · {plan['route']} · {plan['label']}\n")
                for check in plan["checks"]:
                    print(
                        f"[{check['status']}] {check['label']}\n  {check['description']}"
                    )
                for caution in plan["cautions"]:
                    print("! " + caution)
                for phase in plan["phases"]:
                    print("\n" + phase["title"])
                    for index, step in enumerate(phase["steps"], 1):
                        print(f"  {index}. {step}")
                print("\n" + plan["disclaimer"])
            return 3 if plan["blocked"] else 0
        if args.command == "simulate":
            if args.ram is None and args.drive is None:
                raise ValueError("Simulation needs --ram or --drive")
            scenario = simulate(
                hw, result, ram_gb=args.ram, storage=args.drive, reports=reports
            )
            if args.json:
                print(json.dumps(scenario, indent=2, allow_nan=False))
            else:
                print(scenario["note"])
                for change in scenario["changes"]:
                    print(
                        f"{change['name']}: {change['before']} → {change['after']} ({change['delta']:+g} preference points)"
                    )
            return 0
        output_format = "json" if args.json else args.format
        if output_format == "json":
            print(json.dumps(result, indent=2, allow_nan=False))
        elif output_format == "markdown":
            print(markdown_report(result), end="")
        else:
            print(terminal(result))
        return 0 if result["recommendation"] is not None else 3
    except (DetectionError, OSError, ValueError, TypeError) as exc:
        print(f"Compass: {exc}", file=sys.stderr)
        return 2
