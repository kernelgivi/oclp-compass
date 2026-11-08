"""Read-only Darwin probes. Serial numbers and user identifiers never enter profiles."""

from __future__ import annotations
import platform
import plistlib
import shutil
import subprocess
from .schema import Hardware


class DetectionError(RuntimeError):
    pass


def run(argv: list[str]) -> bytes:
    # Executable paths and arguments are compile-time constants at every call site.
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            timeout=20,
            check=True,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DetectionError(f"Hardware probe unavailable: {argv[0]}") from exc
    if len(result.stdout) > 2_000_000:
        raise DetectionError("Hardware probe exceeded output limit")
    return result.stdout


def parse_displays(raw: bytes) -> tuple[str, ...]:
    data = plistlib.loads(raw)
    if not isinstance(data, list):
        return ()
    return tuple(
        str(item.get("sppci_model", item.get("_name", "Unknown GPU")))[:200]
        for section in data
        if isinstance(section, dict)
        for item in section.get("_items", [])
        if isinstance(item, dict)
    )[:8]


def detect() -> Hardware:
    if platform.system() != "Darwin":
        raise DetectionError(
            "Automatic detection requires macOS. Use --demo or --profile for offline evaluation."
        )
    model = run(["/usr/sbin/sysctl", "-n", "hw.model"]).decode().strip()
    ram = int(run(["/usr/sbin/sysctl", "-n", "hw.memsize"])) / 2**30
    notes = [
        "Model identity can be spoofed by OpenCore; confirm the original identifier in OCLP before installing.",
        "Read-only inventory, not a thermal, battery, or disk-health diagnostic.",
    ]
    cpu, cores, avx2, gpus, storage = "Not detected", None, None, (), "unknown"
    try:
        cpu = (
            run(["/usr/sbin/sysctl", "-n", "machdep.cpu.brand_string"]).decode().strip()
        )
        cores = int(run(["/usr/sbin/sysctl", "-n", "hw.physicalcpu"]))
        avx2 = (
            "AVX2"
            in run(["/usr/sbin/sysctl", "-n", "machdep.cpu.leaf7_features"])
            .decode()
            .upper()
        )
    except DetectionError:
        notes.append(
            "CPU capabilities unavailable; compatibility may need manual verification."
        )
    try:
        gpus = parse_displays(
            run(["/usr/sbin/system_profiler", "SPDisplaysDataType", "-xml"])
        )
    except (DetectionError, ValueError, plistlib.InvalidFileException):
        notes.append(
            "GPU probe unavailable. Stock model graphics are only an assumption."
        )
    try:
        disk = plistlib.loads(run(["/usr/sbin/diskutil", "info", "-plist", "/"]))
        # APFS logical volumes often omit this property: never infer SSD from APFS.
        if type(disk.get("SolidState")) is bool:
            storage = "ssd" if disk["SolidState"] else "hdd"
    except (DetectionError, ValueError, plistlib.InvalidFileException):
        pass
    if storage == "unknown":
        notes.append(
            "Boot storage type could not be established; confirm SSD, HDD, or Fusion manually."
        )
    return Hardware(
        model=model,
        ram_gb=round(ram, 1),
        cpu=cpu,
        cores=cores,
        gpus=gpus,
        storage=storage,
        free_gb=round(shutil.disk_usage("/").free / 2**30, 1),
        avx2=avx2,
        arch=platform.machine(),
        current_os=platform.mac_ver()[0] or "Unknown",
        origin="detected",
        notes=tuple(notes),
    )


DEMO = Hardware(
    model="MacBookPro13,3",
    ram_gb=16,
    storage="ssd",
    free_gb=84,
    cpu="Intel Core i7 · Skylake",
    cores=4,
    gpus=("Intel HD Graphics 530", "AMD Radeon Pro 455"),
    avx2=True,
    current_os="15.7",
    origin="demo",
    notes=("Example hardware. No device has been scanned.",),
)
