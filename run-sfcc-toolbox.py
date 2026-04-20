#!/usr/bin/env python3
"""
Unified launcher for SFCC toolbox scripts.

Usage:
- python3 run-sfcc-toolbox.py build
- python3 run-sfcc-toolbox.py import
- python3 run-sfcc-toolbox.py aliases --format "{{brand}}-dev.bollebrands.com"
- python3 run-sfcc-toolbox.py package
"""

import argparse
import os
import subprocess
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
IMPORT_WORKFLOW_SCRIPT = os.path.join(ROOT, "01-import-for-sb", "run-site-import-workflow.py")
ALIASES_SCRIPT = os.path.join(ROOT, "02-aliases-generation", "generate-aliases-from-site-import.py")
PACKAGE_SCRIPT = os.path.join(ROOT, "99-export-zipper", "package-site-exports.py")
DEFAULT_INPUTS_DIR = os.path.join(ROOT, "#INPUTS")
DEFAULT_OUTPUTS_DIR = os.path.join(ROOT, "#OUTPUTS")


def run_script(script_path, extra_args=None):
    cmd = [sys.executable, script_path]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def run_import():
    run_script(IMPORT_WORKFLOW_SCRIPT)


def run_aliases(format_str, input_folder=None, output_folder=None, alone="", hub=""):
    args = ["--format", format_str]
    if input_folder:
        args.extend(["--inputFolder", input_folder])
    if output_folder:
        args.extend(["--outputFolder", output_folder])
    if alone:
        args.extend(["--alone", alone])
    if hub:
        args.extend(["--hub", hub])
    run_script(ALIASES_SCRIPT, args)


def run_package(exports_dir=None, schema_dir=None, skip_validation=False):
    args = []
    if exports_dir:
        args.extend(["--exportsDir", exports_dir])
    if schema_dir:
        args.extend(["--schemaDir", schema_dir])
    if skip_validation:
        args.append("--skipValidation")
    run_script(PACKAGE_SCRIPT, args)


def do_build(args):
    os.makedirs(DEFAULT_INPUTS_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUTS_DIR, exist_ok=True)

    run_import()

    if args.aliases_format:
        run_aliases(
            format_str=args.aliases_format,
            input_folder=args.aliases_input_folder,
            output_folder=args.aliases_output_folder,
            alone=args.alone,
            hub=args.hub,
        )

    run_package(
        exports_dir=args.exports_dir,
        schema_dir=args.schema_dir,
        skip_validation=args.skip_validation,
    )


def main():
    parser = argparse.ArgumentParser(description="Run SFCC toolbox workflows from one command.")
    sub = parser.add_subparsers(dest="command")

    build_parser = sub.add_parser("build", help="Run import workflow, optional aliases, then package outputs.")
    build_parser.add_argument("--aliasesFormat", dest="aliases_format", default="", help="Optional aliases hostname format with {{brand}}.")
    build_parser.add_argument("--aliasesInputFolder", dest="aliases_input_folder", default="", help="Optional folder for aliases generation input.")
    build_parser.add_argument("--aliasesOutputFolder", dest="aliases_output_folder", default="", help="Optional folder for aliases generation output.")
    build_parser.add_argument("--alone", default="", help="Optional aliases 'alone' value.")
    build_parser.add_argument("--hub", default="", help="Optional aliases 'hub' value.")
    build_parser.add_argument("--exportsDir", dest="exports_dir", default="", help="Optional exports directory for packaging.")
    build_parser.add_argument("--schemaDir", dest="schema_dir", default="", help="Optional DWAPP schema directory for validation.")
    build_parser.add_argument("--skipValidation", dest="skip_validation", action="store_true", help="Skip XML validation in package step.")

    aliases_parser = sub.add_parser("aliases", help="Run aliases generation script.")
    aliases_parser.add_argument("--format", required=True, help="Hostname format with {{brand}} placeholder.")
    aliases_parser.add_argument("--inputFolder", dest="input_folder", default="", help="Optional input folder.")
    aliases_parser.add_argument("--outputFolder", dest="output_folder", default="", help="Optional output folder.")
    aliases_parser.add_argument("--alone", default="", help="Optional alone value.")
    aliases_parser.add_argument("--hub", default="", help="Optional hub value.")

    package_parser = sub.add_parser("package", help="Run outputs packaging script.")
    package_parser.add_argument("--exportsDir", dest="exports_dir", default="", help="Optional exports directory.")
    package_parser.add_argument("--schemaDir", dest="schema_dir", default="", help="Optional DWAPP schema directory.")
    package_parser.add_argument("--skipValidation", dest="skip_validation", action="store_true", help="Skip XML validation.")

    sub.add_parser("import", help="Run interactive site-import workflow.")

    parsed = parser.parse_args()
    command = parsed.command or "build"

    if command == "build":
        do_build(parsed)
        return

    if command == "import":
        run_import()
        return

    if command == "aliases":
        run_aliases(
            format_str=parsed.format,
            input_folder=parsed.input_folder,
            output_folder=parsed.output_folder,
            alone=parsed.alone,
            hub=parsed.hub,
        )
        return

    if command == "package":
        run_package(
            exports_dir=parsed.exports_dir,
            schema_dir=parsed.schema_dir,
            skip_validation=parsed.skip_validation,
        )
        return

    parser.error(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
