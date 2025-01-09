"""Console script for access_py_telemetry."""

import access_py_telemetry
from typing import Sequence
from shutil import copy2
import argparse
import filecmp
from pathlib import Path

PACKAGE_ROOT = Path(access_py_telemetry.__file__).parent


def configure_telemetry(argv: Sequence[str] | None = None) -> int:
    """Console script for configuring ipython telemetry."""
    parser = argparse.ArgumentParser(description="Configure ipython telemetry.")
    parser.add_argument("--disable", action="store_true", help="Disable telemetry.")
    parser.add_argument("--enable", action="store_true", help="Enable telemetry.")
    parser.add_argument("--status", action="store_true", help="Check telemetry status.")
    parser.add_argument("--silent", action="store_true", help="Suppress output.")

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
        return 0

    if len([arg for arg in arg_dict.values() if arg]) > 1:
        print("Only one of --disable, --enable, or --status can be used at a time.")
        return 1

    if args.status:
        if telem_file_exists and filecmp.cmp(telemetry_fname, template_file):
            print("Telemetry enabled.") if not args.silent else None
        elif telem_file_exists and not filecmp.cmp(telemetry_fname, template_file):
            (
                print(
                    "Telemetry enabled but misconfigured. Run `access-py-telemetry --disable && access-py-telemetry --enable` to fix."
                )
                if not args.silent
                else None
            )
        else:
            print("Telemetry disabled.") if not args.silent else None
        return 0

    if args.disable:
        if telem_file_exists:
            telemetry_fname.unlink()
            print("Telemetry disabled.") if not args.silent else None
        else:
            print("Telemetry already disabled.") if not args.silent else None
        return 0

    if args.enable:
        if telem_file_exists:
            print("Telemetry already enabled.") if not args.silent else None
            return 0

        if not telemetry_fname.parent.exists():
            telemetry_fname.parent.mkdir(parents=True)
        copy2(template_file, telemetry_fname)
        print("Telemetry enabled.") if not args.silent else None

    return 0
