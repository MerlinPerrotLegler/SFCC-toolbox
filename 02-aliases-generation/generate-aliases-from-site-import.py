#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_SITE_IMPORTS = os.path.join(REPO_ROOT, "#INPUTS")
DEFAULT_OUTPUT_FOLDER = os.path.join(REPO_ROOT, "#OUTPUTS")


def get_ns_prefix(root):
    if "}" in root.tag:
        ns = root.tag.split("}")[0].lstrip("{")
        return f"{{{ns}}}"
    return ""


def parse_site_xml(site_xml_path):
    tree = ET.parse(site_xml_path)
    root = tree.getroot()
    ns = get_ns_prefix(root)
    site_id = root.attrib.get("site-id", "").strip()
    brand_node = root.find(f"{ns}brand")
    brand = (brand_node.text or "").strip() if brand_node is not None else ""
    return site_id, brand


def parse_locales(preferences_xml_path):
    tree = ET.parse(preferences_xml_path)
    root = tree.getroot()
    ns = get_ns_prefix(root)
    pref_nodes = root.findall(
        f".//{ns}standard-preferences/{ns}all-instances/{ns}preference"
    )
    for pref in pref_nodes:
        if pref.attrib.get("preference-id") == "SiteLocales":
            return (pref.text or "").strip()
    return ""


def split_locales(locales_value):
    return [token.strip() for token in locales_value.split(":") if token.strip()]



def discover_candidates(site_imports_root):
    candidates = []
    for current_root, dirs, _ in os.walk(site_imports_root):
        if "sites" in dirs:
            sites_dir = os.path.join(current_root, "sites")
            if not os.path.isdir(sites_dir):
                continue
            site_xml_count = 0
            for site_folder_name in os.listdir(sites_dir):
                site_folder = os.path.join(sites_dir, site_folder_name)
                if not os.path.isdir(site_folder):
                    continue
                site_xml = os.path.join(site_folder, "site.xml")
                if os.path.isfile(site_xml):
                    site_xml_count += 1
            if site_xml_count > 0:
                candidates.append(os.path.abspath(current_root))
    candidates = sorted(set(candidates))
    return candidates


def tty_select_folder(site_imports_root):
    candidates = discover_candidates(site_imports_root)
    if not candidates:
        raise RuntimeError(f"No valid input folder found in: {site_imports_root}")

    print("Select an input folder from #INPUTS:\n")
    for idx, folder in enumerate(candidates, start=1):
        rel = os.path.relpath(folder, REPO_ROOT)
        print(f"{idx:>2}. {rel}")
    print()

    while True:
        raw = input(f"Choice [1-{len(candidates)}]: ").strip()
        if not raw.isdigit():
            print("Please enter a valid number.")
            continue
        idx = int(raw)
        if 1 <= idx <= len(candidates):
            return candidates[idx - 1]
        print("Choice out of range.")


def extract_brand_short_and_zone(site_id):
    match = re.match(r"^(\w+?)_(\w+)$", site_id)
    if not match:
        return "", ""
    brand_short, zone = match.group(1), match.group(2)
    return brand_short, zone


def resolve_input_folder(input_folder):
    """
    Accept both:
    - folder that directly contains 'sites'
    - parent folder that contains exactly one valid child containing 'sites'
    """
    direct_sites = os.path.join(input_folder, "sites")
    if os.path.isdir(direct_sites):
        return input_folder

    valid_children = []
    try:
        children = sorted(os.listdir(input_folder))
    except FileNotFoundError:
        raise RuntimeError(f"Input folder not found: {input_folder}")

    for child in children:
        child_path = os.path.join(input_folder, child)
        if not os.path.isdir(child_path):
            continue
        if os.path.isdir(os.path.join(child_path, "sites")):
            valid_children.append(child_path)

    if len(valid_children) == 1:
        return valid_children[0]

    if len(valid_children) > 1:
        raise RuntimeError(
            "Multiple candidate folders found with a 'sites' subfolder. "
            "Please pass one of them explicitly with --inputFolder:\n"
            + "\n".join(f"- {p}" for p in valid_children)
        )

    raise RuntimeError(f"'sites' folder not found in: {input_folder}")


def find_site_folders(input_folder):
    sites_dir = os.path.join(input_folder, "sites")
    if not os.path.isdir(sites_dir):
        raise RuntimeError(f"'sites' folder not found in: {input_folder}")
    folders = []
    for site_folder_name in sorted(os.listdir(sites_dir)):
        site_folder = os.path.join(sites_dir, site_folder_name)
        if not os.path.isdir(site_folder):
            continue
        if os.path.isfile(os.path.join(site_folder, "site.xml")):
            folders.append(site_folder)
    return folders


def pick_preferences_xml_for_site(input_folder, site_folder, brand_short):
    same_site_pref = os.path.join(site_folder, "preferences.xml")
    if os.path.isfile(same_site_pref):
        return same_site_pref

    sites_dir = os.path.join(input_folder, "sites")
    aa_site_name = f"{brand_short}_AA" if brand_short else ""
    if aa_site_name:
        preferred = os.path.join(sites_dir, aa_site_name, "preferences.xml")
        if os.path.isfile(preferred):
            return preferred

    fallback = os.path.join(sites_dir, "Bolle_AA", "preferences.xml")
    if os.path.isfile(fallback):
        return fallback
    return ""


def build_hostname(format_str, brand_short):
    return format_str.replace("{{brand}}", brand_short.lower())


def group_locales_by_country(locales_list):
    """Returns dict: country_lower -> list of (lang_lower, locale) in insertion order."""
    groups = {}
    for locale in locales_list:
        if "_" in locale:
            lang, country = locale.split("_", 1)
        else:
            lang, country = locale, locale
        key = country.lower()
        if key not in groups:
            groups[key] = []
        groups[key].append((lang.lower(), locale))
    return groups


def _normalize_hostname(hostname):
    return hostname.rstrip("/")


def _join_url(hostname, path):
    hostname = _normalize_hostname(hostname)
    return f"{hostname}{path}"


def build_aliases_json(brand_short, zone, locales_list, format_str):
    hostname = build_hostname(format_str, brand_short)
    zone_upper = zone.upper()
    entries = []

    # Convert locales to language codes preserving order and uniqueness.
    langs = []
    for token in locales_list:
        lang = token.split("_", 1)[0].lower()
        if lang and lang not in langs:
            langs.append(lang)

    if zone_upper == "EU":
        # EU: one entry per language path (/fr/, /de/, ...)
        for lang in langs:
            path = f"/{lang}/"
            entries.append(
                {
                    "brand": brand_short.lower(),
                    "site": zone_upper,
                    "locale": lang,
                    "path": path,
                    "url": _join_url(hostname, path),
                }
            )
    elif zone_upper == "AA":
        # AA: root path only.
        path = "/"
        entries.append(
            {
                "brand": brand_short.lower(),
                "site": zone_upper,
                "locale": langs[0] if langs else "default",
                "path": path,
                "url": _join_url(hostname, path),
            }
        )
    else:
        # Country sites: one path based on site zone (/ca/, /us/, ...)
        path = f"/{zone_upper.lower()}/"
        entries.append(
            {
                "brand": brand_short.lower(),
                "site": zone_upper,
                "locale": langs[0] if langs else zone_upper.lower(),
                "path": path,
                "url": _join_url(hostname, path),
            }
        )

    return json.dumps(entries, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Generate aliases text inputs from a input folder."
    )
    parser.add_argument(
        "--inputFolder",
        dest="input_folder",
        default=None,
        help="Input folder containing a 'sites' directory. Default: TTY selection in ./#INPUTS",
    )
    parser.add_argument(
        "--outputFolder",
        dest="output_folder",
        default=DEFAULT_OUTPUT_FOLDER,
        help="Output folder where the generated text file will be written. Default: ./#OUTPUTS",
    )
    parser.add_argument(
        "--format",
        dest="format_str",
        required=True,
        help="Hostname format string. Use {{brand}} as placeholder. E.g.: {{brand}}-dev.bollebrands.com",
    )
    parser.add_argument(
        "--alone",
        dest="alone",
        default="",
        help="Alone value written in console output.",
    )
    parser.add_argument(
        "--hub",
        dest="hub",
        default="",
        help="Hub value written in console output.",
    )
    args = parser.parse_args()

    if args.input_folder:
        input_folder = os.path.abspath(os.path.expanduser(args.input_folder))
    else:
        input_folder = tty_select_folder(DEFAULT_SITE_IMPORTS)
    input_folder = resolve_input_folder(input_folder)

    output_folder = os.path.abspath(os.path.expanduser(args.output_folder))
    os.makedirs(output_folder, exist_ok=True)

    print(f"outputFolder: {output_folder}")
    print(f"inputFolder: {input_folder}")
    print(f"hub: {args.hub}")
    print(f"alone: {args.alone}")

    site_folders = find_site_folders(input_folder)
    if not site_folders:
        print(f"No site.xml found under: {os.path.join(input_folder, 'sites')}")
        sys.exit(1)

    generated_count = 0
    for site_folder in site_folders:
        site_xml_path = os.path.join(site_folder, "site.xml")
        site_id, brand = parse_site_xml(site_xml_path)
        if not site_id:
            continue
        brand_short, zone = extract_brand_short_and_zone(site_id)
        preferences_xml_path = pick_preferences_xml_for_site(
            input_folder, site_folder, brand_short
        )
        locales_raw = parse_locales(preferences_xml_path) if preferences_xml_path else ""
        locales_list = split_locales(locales_raw)

        content = build_aliases_json(
            brand_short=brand_short,
            zone=zone,
            locales_list=locales_list,
            format_str=args.format_str,
        )

        aliases_file = os.path.join(
            output_folder, "alias-input", "sites", site_id, "urls", "aliases"
        )
        os.makedirs(os.path.dirname(aliases_file), exist_ok=True)
        with open(aliases_file, "w", encoding="utf-8") as f:
            f.write(content)
        generated_count += 1

    print(f"Generated aliases files: {generated_count}")


if __name__ == "__main__":
    main()
