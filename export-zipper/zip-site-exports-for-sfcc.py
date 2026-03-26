#!/usr/bin/env python3
"""
Zip all folders in site-exports for SFCC import.

Rules:
- Never remove source folders.
- On each execution, remove all .zip files from site-exports first.
- Validate XML files with DWAPP-schema when possible.
"""

import argparse
import os
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORTS_DIR = REPO_ROOT / "site-exports"
DEFAULT_SCHEMA_DIR = REPO_ROOT / "DWAPP-schema"


def remove_existing_zips(exports_dir: Path) -> int:
    removed = 0
    for item in exports_dir.glob("*.zip"):
        item.unlink()
        removed += 1
    return removed


def discover_xsd_files(schema_dir: Path) -> dict:
    mapping = {}
    for xsd in schema_dir.glob("*.xsd"):
        key = normalize_name(xsd.stem)
        mapping[key] = xsd
    return mapping


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def guess_xsd_for_xml(xml_path: Path, root_tag: str, xsd_by_name: dict) -> Path | None:
    # Priority 1: match by filename stem
    stem_key = normalize_name(xml_path.stem)
    if stem_key in xsd_by_name:
        return xsd_by_name[stem_key]

    # Priority 2: match by root tag
    root_key = normalize_name(root_tag)
    if root_key in xsd_by_name:
        return xsd_by_name[root_key]

    return None


def get_root_tag(xml_path: Path) -> str:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if "}" in root.tag:
        return root.tag.split("}", 1)[1]
    return root.tag


def validate_xml_files(exports_dir: Path, schema_dir: Path) -> tuple[int, int]:
    """
    Returns (validated_count, failed_count).
    If lxml is unavailable, XML validation is skipped.
    """
    try:
        from lxml import etree  # type: ignore
    except Exception:
        print("⚠️  lxml not installed: XML schema validation skipped.")
        return 0, 0

    if not schema_dir.is_dir():
        print(f"⚠️  Schema folder not found: {schema_dir}. Validation skipped.")
        return 0, 0

    xsd_by_name = discover_xsd_files(schema_dir)
    validated = 0
    failed = 0

    for xml_path in exports_dir.rglob("*.xml"):
        try:
            root_tag = get_root_tag(xml_path)
            xsd_path = guess_xsd_for_xml(xml_path, root_tag, xsd_by_name)
            if xsd_path is None:
                # No matching schema: skip file (not counted as failure)
                continue

            schema_doc = etree.parse(str(xsd_path))
            schema = etree.XMLSchema(schema_doc)
            xml_doc = etree.parse(str(xml_path))

            if schema.validate(xml_doc):
                validated += 1
            else:
                failed += 1
                errors = "; ".join(
                    f"{e.line}:{e.column} {e.message}" for e in schema.error_log
                )
                print(f"❌ XML invalid: {xml_path} (schema: {xsd_path.name})")
                if errors:
                    print(f"   {errors}")
        except Exception as exc:
            failed += 1
            print(f"❌ Validation error: {xml_path} -> {exc}")

    return validated, failed


def zip_folder(source_folder: Path, output_zip: Path) -> None:
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_folder.rglob("*"):
            if not file_path.is_file():
                continue
            # Include top-level folder in archive name (SFCC import-friendly)
            arcname = source_folder.name + "/" + str(file_path.relative_to(source_folder))
            zf.write(file_path, arcname=arcname)


def zip_all_top_level_folders(exports_dir: Path) -> int:
    created = 0
    for item in sorted(exports_dir.iterdir()):
        if item.is_dir():
            output_zip = exports_dir / f"{item.name}.zip"
            zip_folder(item, output_zip)
            created += 1
            print(f"✅ Created: {output_zip.name}")
    return created


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Zip all site-exports folders for SFCC import."
    )
    parser.add_argument(
        "--exportsDir",
        default=str(DEFAULT_EXPORTS_DIR),
        help="Folder containing export folders to zip (default: ./site-exports).",
    )
    parser.add_argument(
        "--schemaDir",
        default=str(DEFAULT_SCHEMA_DIR),
        help="DWAPP schema folder used for XML validation (default: ./DWAPP-schema).",
    )
    parser.add_argument(
        "--skipValidation",
        action="store_true",
        help="Skip XML validation against DWAPP-schema.",
    )
    args = parser.parse_args()

    exports_dir = Path(os.path.abspath(os.path.expanduser(args.exportsDir)))
    schema_dir = Path(os.path.abspath(os.path.expanduser(args.schemaDir)))

    if not exports_dir.is_dir():
        print(f"❌ Exports folder not found: {exports_dir}")
        sys.exit(1)

    removed = remove_existing_zips(exports_dir)
    print(f"🧹 Removed old zip files: {removed}")

    if not args.skipValidation:
        validated, failed = validate_xml_files(exports_dir, schema_dir)
        print(f"🔎 XML validated: {validated}, failed: {failed}")
        if failed > 0:
            print("❌ Stop: XML validation failed.")
            sys.exit(1)

    created = zip_all_top_level_folders(exports_dir)
    print(f"📦 Total zip files created: {created}")
    print("Done. Source folders are kept unchanged.")


if __name__ == "__main__":
    main()
