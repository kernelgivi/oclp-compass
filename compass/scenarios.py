"""Sensitivity analysis for a hypothetical RAM/drive configuration.

A simulated configuration says nothing about whether parts can be replaced in a
particular Mac. Soldered RAM and drive restrictions need a separate hardware check.
"""

from __future__ import annotations

from dataclasses import replace

from .engine import recommend
from .schema import Hardware


def simulate(
    hardware: Hardware,
    baseline: dict,
    *,
    ram_gb=None,
    storage=None,
    reports=None,
    today=None,
):
    proposed = replace(
        hardware,
        ram_gb=hardware.ram_gb if ram_gb is None else ram_gb,
        storage=hardware.storage if storage is None else storage,
        origin="manual",
        notes=(
            "Hypothetical configuration. Verify physical upgradeability separately.",
        ),
    )
    projected = recommend(
        proposed,
        priority=baseline["priority"],
        min_os=baseline["min_os"],
        reports=reports,
        today=today,
        requirements=baseline["requirements"],
    )
    original = {item["major"]: item for item in baseline["candidates"]}
    changes = [
        {
            "major": item["major"],
            "name": item["name"],
            "before": original[item["major"]]["score"],
            "after": item["score"],
            "delta": round(item["score"] - original[item["major"]]["score"], 2),
            "eligible_before": original[item["major"]]["eligible"],
            "eligible_after": item["eligible"],
        }
        for item in projected["candidates"]
        if item["major"] in original
    ]
    return {
        "baseline": hardware.to_dict(),
        "proposed": proposed.to_dict(),
        "recommendation_before": baseline["recommendation"],
        "recommendation_after": projected["recommendation"],
        "changes": changes,
        "note": "Hypothetical preference-index changes, not benchmark gains. RAM may be soldered and drives may be restricted; verify your exact model before buying parts. Evidence weights can also change when the proposed configuration differs from owner reports.",
    }
