"""Console script for access_ipy_telemetry."""

import access_ipy_telemetry
from typing import Sequence
from shutil import copy2
import argparse
import filecmp
from pathlib import Path

PACKAGE_ROOT = Path(access_ipy_telemetry.__file__).parent.parent.parent


def configure_telemetry(argv: Sequence[str] | None = None) -> int:
    """Console script for configuring ipython telemetry."""
    parser = argparse.ArgumentParser(description="Configure ipython telemetry.")
    parser.add_argument("--disable", action="store_true", help="Disable telemetry.")
    parser.add_argument("--enable", action="store_true", help="Enable telemetry.")
    parser.add_argument("--status", action="store_true", help="Check telemetry status.")

    HOME = Path.home()
    telemetry_fname = HOME / ".ipython" / "profile_default" / "startup" / "telemetry.py"
    template_file = PACKAGE_ROOT / "templates" / "telemetry_template.py"
    telem_file_exists = telemetry_fname.exists()

    args = parser.parse_args(argv)

    arg_dict = {
        "disable": args.disable,
        "enable": args.enable,
        "status": args.status,
    }

    if not any(arg_dict.values()):
        parser.print_help()
        print()
        return 0

    if len([arg for arg in arg_dict.values() if arg]) > 1:
        print("Only one of --disable, --enable, or --status can be used at a time.")
        return 1

    if args.status:
        if telem_file_exists and filecmp.cmp(telemetry_fname, template_file):
            print("Telemetry enabled.")
        elif telem_file_exists and not filecmp.cmp(telemetry_fname, template_file):
            print(
                "Telemetry enabled but misconfigured. Run `access_ipy_telemetry --disable && access_ipy_telemetry --enable` to fix."
            )
        else:
            print("Telemetry disabled.")
        return 0

    if args.disable:
        if telem_file_exists:
            telemetry_fname.unlink()
            print("Telemetry disabled.")
        else:
            print("Telemetry already disabled.")
        return 0

    if args.enable:
        if telem_file_exists:
            print("Telemetry already enabled.")
            return 0

        if not telemetry_fname.parent.exists():
            telemetry_fname.parent.mkdir(parents=True)
        copy2(template_file, telemetry_fname)
        print("Telemetry enabled.")

    return 0


if __name__ == "__main__":
    configure_telemetry()
