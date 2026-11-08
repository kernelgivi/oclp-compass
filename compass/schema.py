"""Strict boundaries for hardware profiles and untrusted evidence imports."""

from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from urllib.parse import urlsplit

MODEL = re.compile(
    r"(?:MacBookPro|MacBookAir|MacBook|Macmini|MacPro|iMacPro|iMac|Xserve|Mac|VirtualMac)\d{1,2},\d{1,2}\Z"
)
MAX_FILE = 2_000_000


def load_json(path: Path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    if len(raw) > MAX_FILE:
        raise ValueError("JSON exceeds the 2 MB limit")
    return strict_json_loads(raw)


def strict_json_loads(raw):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise ValueError("Non-finite numbers are not valid JSON")

    return json.loads(
        raw, object_pairs_hook=object_pairs, parse_constant=invalid_constant
    )


def text(value, name, limit=200):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(c) < 32 for c in value)
    ):
        raise ValueError(f"Invalid {name}")
    return value


def number(value, name, low, high):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise ValueError(f"Invalid {name}: expected {low}–{high}")
    return value


def source_url(value):
    text(value, "source URL", 1000)
    if any(c.isspace() or c in "<>\\" for c in value):
        raise ValueError("Source URL contains unsafe characters")
    u = urlsplit(value)
    if (
        u.scheme != "https"
        or u.hostname
        not in {
            "www.reddit.com",
            "reddit.com",
            "github.com",
            "forums.macrumors.com",
            "dortania.github.io",
            "support.apple.com",
        }
        or u.username
        or u.password
        or u.port not in (None, 443)
        or u.query
        or u.fragment
    ):
        raise ValueError(
            "Source must be an HTTPS permalink on an approved community/documentation host, without query or fragment"
        )
    return value


@dataclass(frozen=True)
class Hardware:
    model: str
    ram_gb: float
    storage: str = "unknown"
    free_gb: float | None = None
    cpu: str = "Not detected"
    cores: int | None = None
    gpus: tuple[str, ...] = ()
    arch: str = "x86_64"
    current_os: str = "Unknown"
    avx2: bool | None = None
    origin: str = "manual"
    notes: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.model, str) or not MODEL.fullmatch(self.model):
            raise ValueError(
                "Expected a Mac model identifier, for example MacBookPro13,3"
            )
        number(self.ram_gb, "RAM", 1, 2048)
        if self.storage not in {"ssd", "hdd", "fusion", "unknown"}:
            raise ValueError("Invalid storage type")
        if self.free_gb is not None:
            number(self.free_gb, "free space", 0, 1_000_000)
        if self.cores is not None:
            number(self.cores, "cores", 1, 512)
        for name in ("cpu", "arch", "current_os", "origin"):
            text(getattr(self, name), name)
        if self.arch not in {"x86_64", "arm64", "unknown"} or self.origin not in {
            "manual",
            "detected",
            "demo",
        }:
            raise ValueError("Invalid architecture or profile origin")
        if self.avx2 is not None and type(self.avx2) is not bool:
            raise ValueError("Invalid AVX2 flag")
        if not isinstance(self.gpus, (list, tuple)) or len(self.gpus) > 8:
            raise ValueError("Invalid GPUs")
        if not isinstance(self.notes, (list, tuple)) or len(self.notes) > 30:
            raise ValueError("Invalid notes")
        for item in (*self.gpus, *self.notes):
            text(item, "profile field", 500)

    def to_dict(self):
        value = asdict(self)
        value["gpus"] = list(self.gpus)
        value["notes"] = list(self.notes)
        return value

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict) or set(value) - set(cls.__dataclass_fields__):
            raise ValueError("Unknown hardware fields")
        return cls(**value)
