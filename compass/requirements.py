"""User-supplied app requirements are constraints, never inferred certifications."""

from .schema import text


def validate_requirements(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError("Expected up to 100 essential app requirements")
    names = set()
    for app in value:
        if not isinstance(app, dict) or set(app) != {"name", "min_os", "avx2", "metal"}:
            raise ValueError("Each app must contain name, min_os, avx2, and metal")
        text(app["name"], "app name", 100)
        if type(app["min_os"]) is not int or app["min_os"] not in {
            11,
            12,
            13,
            14,
            15,
            26,
        }:
            raise ValueError("Invalid minimum app OS")
        if type(app["avx2"]) is not bool or type(app["metal"]) is not bool:
            raise ValueError("App AVX2 and Metal requirements must be booleans")
        if app["name"].casefold() in names:
            raise ValueError("Duplicate essential app name")
        names.add(app["name"].casefold())
    return value
