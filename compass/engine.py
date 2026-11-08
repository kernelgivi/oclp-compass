"""Deterministic ranking. Scores express policy preferences, never measured FPS."""

from __future__ import annotations
from datetime import date
from importlib.resources import files
import json
from .evidence import summarize, validate_reports
from .requirements import validate_requirements
from .schema import Hardware

PROFILES = {
    "balanced": (0.45, 0.35, 0.20),
    "smoothness": (0.75, 0.10, 0.15),
    "apps": (0.20, 0.65, 0.15),
}


def data(name):
    return json.loads(files("compass").joinpath("data", name + ".json").read_text())


def recommend(
    hw: Hardware,
    priority="balanced",
    min_os=11,
    reports=None,
    today=None,
    requirements=None,
):
    today = today or date.today()
    if priority not in PROFILES:
        raise ValueError("Unknown priority")
    if type(min_os) is not int or min_os not in {11, 12, 13, 14, 15, 26}:
        raise ValueError("Invalid minimum macOS version")
    requirements = validate_requirements([] if requirements is None else requirements)
    policy, models = data("policy"), data("models")
    reports = validate_reports(data("reports") if reports is None else reports, today)
    age = (today - date.fromisoformat(policy["reviewed"])).days
    result = {
        "hardware": hw.to_dict(),
        "priority": priority,
        "min_os": min_os,
        "policy": policy,
        "policy_age_days": age,
        "stale": age > 90,
        "candidates": [],
        "recommendation": None,
        "requirements": requirements,
        "warnings": list(hw.notes),
        "weights": dict(
            zip(("smoothness", "app_recency", "maintenance"), PROFILES[priority])
        ),
        "checklist": [
            "Back up with Time Machine and verify that you can restore.",
            "Update to the latest native macOS first to obtain firmware updates.",
            "Confirm the original model and actual GPU against Dortania; modified GPUs need individual review.",
            "Check each essential app's OS, CPU instruction, and GPU requirements with its vendor.",
            "Read the current OCLP release notes and prepare recovery media before installation.",
        ],
    }
    if age < 0:
        result["warnings"].append(
            "Local clock predates the policy snapshot; check the system date."
        )
    if age > 90:
        result["warnings"].append(
            "Policy snapshot is over 90 days old. Verify upstream support before acting."
        )
    if hw.arch == "arm64":
        result["status"] = "apple_silicon"
        result["warnings"].append(
            "OCLP does not support Apple Silicon. Use Apple's native upgrade path."
        )
        return result
    spec = models.get(hw.model)
    if not spec:
        result["status"] = "unreviewed"
        result["warnings"].append(
            "This model has no reviewed policy in Compass. This does not mean OCLP cannot support it; consult the official model list."
        )
        return result
    if hw.arch != "x86_64":
        result["status"] = "unreviewed"
        result["warnings"].append(
            "CPU architecture is unknown. No installation recommendation can be made."
        )
        return result
    result["status"] = "ranked"
    result["model"] = spec
    result["warnings"] += [
        "Performance scores are transparent heuristics, not benchmarks or guarantees.",
        "App recency measures OS age only; it does not certify any application or security-update coverage.",
        "Stock graphics policy: GPU swaps and disabled/failing GPUs require manual review.",
        "Community reports are anecdotal and self-selected. The bundled corpus is intentionally small.",
    ]
    if hw.free_gb is not None and hw.free_gb < 45:
        result["warnings"].append(
            "Less than 45 GiB free: planning warning, not an installer requirement. Check target-specific space needs."
        )
    if hw.storage in {"hdd", "fusion", "unknown"}:
        result["warnings"].append(
            "Storage is a major source of uncertainty; SSDs generally reduce disk bottlenecks. Confirm the boot drive type."
        )
    if hw.avx2 is False:
        result["warnings"].append(
            "CPU lacks AVX2. Some newer applications may fail regardless of OS installation success."
        )
    for os in policy["systems"]:
        major = os["major"]
        experimental = os.get("experimental", False)
        patched = major > spec["native_max"]
        graphics = (
            spec["graphics_patch_from"] is not None
            and major >= spec["graphics_patch_from"]
        )
        reasons, blocks = [], []
        app_checks = []
        for app in requirements:
            unmet, unknown = [], []
            if major < app["min_os"]:
                unmet.append("requires a newer macOS")
            if app["avx2"] and hw.avx2 is False:
                unmet.append("requires AVX2, which this CPU lacks")
            elif app["avx2"] and hw.avx2 is None:
                unknown.append("AVX2 capability is unknown")
            if app["metal"] and spec["gpu_class"] == "non_metal":
                unmet.append("requires Metal; stock GPU is non-Metal")
            blocks.extend(app["name"] + ": " + message for message in unmet)
            # Unknown essential capabilities cannot produce an affirmative recommendation.
            blocks.extend(
                app["name"] + ": " + message + "; verify before ranking"
                for message in unknown
            )
            app_checks.append(
                {
                    "name": app["name"],
                    "status": (
                        "blocked"
                        if unmet
                        else "unknown" if unknown else "meets_declared_requirements"
                    ),
                    "notes": unmet + unknown,
                }
            )
        if major < min_os:
            blocks.append("Below your selected minimum OS requirement")
        if major >= 14 and hw.ram_gb < 3:
            blocks.append(
                "Dortania requires at least 3 GB RAM for Sonoma and newer installation"
            )
        if experimental:
            blocks.append(
                "Tahoe support is prerelease in the reviewed upstream snapshot; excluded from recommendations"
            )
        if major < 14:
            reasons.append(
                "Older OS: verify current security updates and essential app availability independently"
            )
        if patched:
            reasons.append(
                "Requires OCLP: maintenance differs from an Apple-supported installation"
            )
        if graphics:
            reasons.append(
                "Stock graphics need root patches; OS updates can require repatching"
            )
        if spec["gpu_class"] == "non_metal":
            reasons.append(
                "Non-Metal GPU: Metal-dependent applications and visual features may not work"
            )
        if (
            hw.model
            in {"MacBookPro13,2", "MacBookPro13,3", "MacBookPro14,2", "MacBookPro14,3"}
            and major >= 14
        ):
            reasons.append(
                "T1 / Touch Bar: verify release-specific Touch ID and Apple Pay behavior"
            )
        if hw.model in {"Macmini5,1", "Macmini5,2", "Macmini5,3"} and major >= 13:
            reasons.append(
                "Legacy USB 1.1: installer input may require a USB 2.0 hub and external input devices"
            )
        if hw.model in {"MacBookPro8,2", "MacBookPro8,3"}:
            reasons.append(
                "2011 dual-GPU hardware: known dGPU failure and switching limitations require individual review"
            )
        if patched and major >= 14:
            reasons.append(
                "Verify wireless card support and release-specific root patches; graphics policy alone is not a full patch inventory"
            )
        evidence = summarize(reports, hw, major, today)
        ram_penalty = (
            22 if hw.ram_gb < 4 else 14 if hw.ram_gb < 8 else 5 if hw.ram_gb < 16 else 0
        )
        disk_penalty = {"ssd": 0, "hdd": 18, "fusion": 12, "unknown": 7}[hw.storage]
        os_load = {11: 0, 12: 3, 13: 9, 14: 14, 15: 18, 26: 30}[major]
        graphics_penalty = (
            18 if spec["gpu_class"] == "non_metal" else 6 if graphics else 0
        )
        base = (
            spec["capacity"]
            + 10
            - ram_penalty
            - disk_penalty
            - os_load
            - graphics_penalty
        )
        smooth = round(max(0, min(100, base + evidence["adjustment"])), 1)
        maintenance = max(
            0,
            95
            - (20 if patched else 0)
            - (18 if graphics else 0)
            - (12 if spec["gpu_class"] == "non_metal" else 0),
        )
        score = round(
            sum(
                a * b
                for a, b in zip(
                    PROFILES[priority], (smooth, os["recency"], maintenance)
                )
            ),
            1,
        )
        result["candidates"].append(
            {
                **os,
                "route": "OCLP" if patched else "Native",
                "graphics_patches": graphics,
                "smoothness": smooth,
                "app_recency": os["recency"],
                "maintenance": maintenance,
                "score": score,
                "eligible": not blocks,
                "blocks": blocks,
                "app_checks": app_checks,
                "reasons": reasons,
                "evidence": evidence,
                "calculation": {
                    "capacity": spec["capacity"],
                    "headroom": 10,
                    "ram_penalty": ram_penalty,
                    "storage_penalty": disk_penalty,
                    "os_load": os_load,
                    "graphics_penalty": graphics_penalty,
                    "community_adjustment": evidence["adjustment"],
                },
            }
        )
    result["candidates"].sort(
        key=lambda r: (r["eligible"], r["score"], r["major"]), reverse=True
    )
    eligible = [r for r in result["candidates"] if r["eligible"]]
    if eligible:
        result["recommendation"] = eligible[0]["major"]
    else:
        result["warnings"].append("No reviewed stable option meets your constraints.")
    return result
