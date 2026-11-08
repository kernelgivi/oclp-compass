"""Explain decisions and build reviewable plans without changing the machine.

These helpers consume an engine result. They do not probe hardware or infer that a
backup, patch, installation, or application test has actually been completed.
"""

from __future__ import annotations

import re
from typing import Any

CONFIRMATIONS = {
    "backup": "I have verified a current backup and know how to restore it.",
    "identity": "I have checked the original model and actual graphics hardware.",
    "apps": "I have checked my essential apps and peripherals with their vendors.",
    "recovery": "I have prepared and checked a recovery method.",
}

METRICS = {
    "smoothness": "Estimated smoothness",
    "app_recency": "OS recency",
    "maintenance": "Maintenance ease",
    "score": "Weighted fit",
}


def candidate(result: dict[str, Any], major: int) -> dict[str, Any]:
    if type(major) is not int:
        raise ValueError("macOS major must be an integer")
    for item in result["candidates"]:
        if item["major"] == major:
            return item
    raise ValueError("The selected macOS has no reviewed candidate for this model")


def compare(result: dict[str, Any], left: int, right: int) -> dict[str, Any]:
    """Return signed right-minus-left preference deltas, not speed measurements."""
    if left == right:
        raise ValueError("Choose two different macOS versions")
    a, b = candidate(result, left), candidate(result, right)
    eligible = [item for item in (a, b) if item["eligible"]]
    winner = (
        max(eligible, key=lambda item: (item["score"], item["major"]))
        if eligible
        else None
    )
    differences = []
    if a["route"] != b["route"]:
        differences.append(
            f"{a['name']} uses the {a['route']} path; {b['name']} uses the {b['route']} path."
        )
    if a["graphics_patches"] != b["graphics_patches"]:
        patched = a if a["graphics_patches"] else b
        differences.append(
            f"{patched['name']} needs stock graphics root patches under this policy."
        )
    if a["evidence"]["independent"] != b["evidence"]["independent"]:
        differences.append(
            "The two versions have different numbers of exact-model owner reports. Check the sample sizes."
        )
    for item in (a, b):
        if not item["eligible"]:
            differences.append(
                f"{item['name']} is excluded: " + "; ".join(item["blocks"])
            )
    return {
        "left": a,
        "right": b,
        "metrics": [
            {
                "key": key,
                "label": label,
                "left": a[key],
                "right": b[key],
                "delta": round(b[key] - a[key], 2),
            }
            for key, label in METRICS.items()
        ],
        "preferred": winner["major"] if winner else None,
        "differences": differences,
        "note": "All deltas are preference-index points. They are not percentages, FPS, or benchmark gains.",
    }


def build_plan(
    result: dict[str, Any], target: int, confirmations=None
) -> dict[str, Any]:
    selected = candidate(result, target)
    confirmations = {} if confirmations is None else confirmations
    if not isinstance(confirmations, dict) or set(confirmations) - set(CONFIRMATIONS):
        raise ValueError("Unknown planning confirmation")
    if any(type(value) is not bool for value in confirmations.values()):
        raise ValueError("Planning confirmations must be booleans")

    checks = [
        {
            "id": "compatibility",
            "label": "Reviewed compatibility",
            "status": "pass" if selected["eligible"] else "blocked",
            "description": (
                "This option meets the currently declared model, OS, RAM, and app constraints."
                if selected["eligible"]
                else "; ".join(selected["blocks"])
            ),
        },
        {
            "id": "policy",
            "label": "Policy freshness",
            "status": (
                "review" if result["stale"] or result["policy_age_days"] < 0 else "pass"
            ),
            "description": f"Snapshot reviewed {result['policy']['reviewed']}. Check upstream release notes before installation.",
        },
    ]
    free = result["hardware"]["free_gb"]
    checks.append(
        {
            "id": "space",
            "label": "Working space",
            "status": "review" if free is None or free < 45 else "pass",
            "description": (
                "Free space is unknown. Verify installer and working-space requirements."
                if free is None
                else f"{free:g} GiB available. The 45 GiB planning threshold is advisory, not an installer requirement."
            ),
        }
    )
    checks.extend(
        {
            "id": key,
            "label": label,
            "status": "confirmed" if confirmations.get(key) else "review",
            "description": (
                "Confirmed by you for this target and session; Compass has not independently verified it."
                if confirmations.get(key)
                else "Requires your confirmation after checking it yourself."
            ),
        }
        for key, label in CONFIRMATIONS.items()
    )
    current = result["hardware"]["current_os"]
    match = re.match(r"^(\d+)(?:\.|$)", current)
    current_major = int(match[1]) if match else None
    direction = (
        "unknown"
        if current_major is None
        else (
            "downgrade"
            if target < current_major
            else "same_major" if target == current_major else "upgrade"
        )
    )
    cautions = list(selected["reasons"])
    if direction == "downgrade":
        cautions.insert(
            0,
            "This is a downgrade. Do not assume an in-place downgrade will preserve data; review a separate volume or clean-install recovery plan.",
        )
    if direction == "same_major":
        cautions.insert(
            0,
            "The selected major version is already installed. Compass has not verified its build, patch state, or stability; reinstalling is not automatically beneficial.",
        )
    if result["hardware"]["origin"] != "detected":
        cautions.insert(
            0,
            "This plan uses example or manually supplied hardware. Confirm it against the physical Mac.",
        )

    prepare = [
        "Check the current OCLP release notes and the original model's known issues.",
        "Finish the review items above and test your recovery method before changing disks or software.",
        "Confirm installer requirements, free space, and essential application versions for this exact target build.",
    ]
    if selected["route"] == "OCLP":
        installation = [
            "Follow Dortania's guide to obtain the target installer and build OpenCore for the original model.",
            "Review the documented boot/recovery process and install onto the intended, backed-up volume.",
            "Use the matching OCLP release to check required post-install root patches, then follow its reboot instructions.",
        ]
    else:
        installation = [
            "Use Apple's documented installer or upgrade method for this natively supported target.",
            "If OpenCore is already present, review Dortania's documented migration/uninstall guidance before changing the boot setup.",
        ]
    validation = [
        "Check graphics acceleration, brightness, sleep/wake, Wi-Fi, Bluetooth, audio, and external displays.",
        "Run your essential applications and peripherals before relying on this installation.",
        "Allow initial indexing to finish before judging responsiveness; compare the same workload and power state.",
        "Keep the verified backup and recovery method available until the system has proved reliable.",
    ]
    blocked = any(check["status"] == "blocked" for check in checks)
    outstanding = sum(check["status"] == "review" for check in checks)
    return {
        "target": target,
        "name": selected["name"],
        "route": selected["route"],
        "direction": direction,
        "checks": checks,
        "cautions": cautions,
        "blocked": blocked,
        "outstanding": outstanding,
        "state": (
            "blocked"
            if blocked
            else "needs_review" if outstanding else "checklist_complete"
        ),
        "label": (
            "Target excluded"
            if blocked
            else (
                f"{outstanding} items need review"
                if outstanding
                else "Planning checklist complete"
            )
        ),
        "phases": [{"id": "prepare", "title": "Prepare", "steps": prepare}]
        + (
            []
            if blocked
            else [
                {
                    "id": "install",
                    "title": "Follow the official installation guide",
                    "steps": installation,
                },
                {"id": "validate", "title": "Validate the result", "steps": validation},
            ]
        ),
        "disclaimer": "This is a planning aid, not permission or proof that installation is safe. No disks, boot settings, or patches are modified.",
    }


def _escape(value) -> str:
    value = str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>-])", r"\\\1", value).replace("\n", " ")


def markdown_report(result: dict[str, Any], plan=None) -> str:
    hw = result["hardware"]
    lines = [
        "# OCLP Compass analysis",
        "",
        f"Model: {_escape(hw['model'])} · source: {_escape(hw['origin'])}",
        f"RAM: {hw['ram_gb']:g} GiB · storage: {_escape(hw['storage'])} · current macOS: {_escape(hw['current_os'])}",
        f"Policy: {_escape(result['policy']['reviewed'])} · priority: {_escape(result['priority'])}",
        "",
        "Scores are preference estimates, not measured speed or verified application support.",
        "",
        "| macOS | Path | Smoothness | OS recency | Maintenance | Fit | Eligible |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in result["candidates"]:
        lines.append(
            f"| {_escape(item['name'])} | {item['route']} | {item['smoothness']} | {item['app_recency']} | {item['maintenance']} | {item['score']} | {'Yes' if item['eligible'] else 'No'} |"
        )
    for item in result["candidates"]:
        lines.extend(["", f"## {_escape(item['name'])}", ""])
        lines.extend(
            "- " + _escape(message) for message in item["blocks"] + item["reasons"]
        )
        evidence = item["evidence"]
        lines.extend(
            [
                "",
                f"Independent owner reports: {evidence['independent']}; effective sample: {evidence['effective_sample']}; community adjustment: {evidence['adjustment']} points.",
            ]
        )
        for report in evidence["reports"]:
            lines.extend(
                ["", _escape(report["summary"]), "", "Source: <" + report["url"] + ">"]
            )
    lines.extend(["", "## Warnings", ""])
    lines.extend("- " + _escape(message) for message in result["warnings"])
    if plan:
        lines.extend(
            ["", f"## Plan: {_escape(plan['name'])}", "", _escape(plan["label"]), ""]
        )
        for check in plan["checks"]:
            mark = "x" if check["status"] in {"pass", "confirmed"} else " "
            lines.append(
                f"- [{mark}] {_escape(check['label'])} — {_escape(check['description'])}"
            )
        for phase in plan["phases"]:
            lines.extend(["", "### " + _escape(phase["title"]), ""])
            lines.extend(
                f"{index}. {_escape(step)}"
                for index, step in enumerate(phase["steps"], 1)
            )
        lines.extend(["", _escape(plan["disclaimer"])])
    lines.extend(["", "## References", ""])
    lines.extend(
        f"- {_escape(source['title'])}: <{source['url']}>"
        for source in result["policy"]["sources"]
    )
    return "\n".join(lines) + "\n"
