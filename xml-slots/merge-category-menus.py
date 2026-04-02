#!/usr/bin/env python3

import argparse
import copy
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple
from xml.etree import ElementTree as ET


def _ns_uri_from_tag(tag: str) -> str:
    # tag is like "{http://...}slot-configurations"
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return ""


def q(ns_uri: str, local: str) -> str:
    return f"{{{ns_uri}}}{local}" if ns_uri else local


def normalize_xml(xml: str) -> str:
    # Collapse whitespace to make dedupe more robust to formatting.
    return re.sub(r"\s+", "", xml).strip()


def custom_attribute_dedupe_key(attr_el: ET.Element) -> str:
    attr_id = attr_el.get("attribute-id", "")
    # Include full structure (incl. nested <value>) to avoid collisions.
    serialized = ET.tostring(attr_el, encoding="unicode", method="xml")
    return f"{attr_id}::{normalize_xml(serialized)}"


def merge_slot_group(
    ns_uri: str,
    group_key: Tuple[str, str],
    candidates: List[ET.Element],
    template_text: str,
) -> ET.Element:
    # group_key = (context-id, configuration-id)
    context_id, configuration_id = group_key

    rep = candidates[0]
    out = ET.Element(q(ns_uri, "slot-configuration"))

    # slot attributes
    out.set("slot-id", "category-menu")
    out.set("context", rep.get("context", "category"))
    out.set("context-id", context_id)
    out.set("configuration-id", configuration_id)

    # Merge common boolean-ish flags
    assigned_to_site_values = [c.get("assigned-to-site") for c in candidates if c.get("assigned-to-site") is not None]
    assigned_to_site = "true" if any(v == "true" for v in assigned_to_site_values) else "false"
    out.set("assigned-to-site", assigned_to_site)

    default_values = [c.get("default") for c in candidates if c.get("default") is not None]
    if any(v == "true" for v in default_values):
        out.set("default", "true")

    enabled_flag_values = []
    for c in candidates:
        ef = c.find(q(ns_uri, "enabled-flag"))
        if ef is not None and ef.text is not None:
            enabled_flag_values.append(ef.text.strip())
    enabled_flag = "true" if any(v == "true" for v in enabled_flag_values) else "false"

    # Template
    template_el = ET.SubElement(out, q(ns_uri, "template"))
    template_el.text = template_text

    enabled_el = ET.SubElement(out, q(ns_uri, "enabled-flag"))
    enabled_el.text = enabled_flag

    # Content: merge content-assets/content-asset content-id
    merged_assets: List[str] = []
    seen_assets = set()
    for c in candidates:
        for asset_el in c.findall(f".//{q(ns_uri, 'content-assets')}/{q(ns_uri, 'content-asset')}"):
            content_id = asset_el.get("content-id")
            if not content_id:
                continue
            if content_id in seen_assets:
                continue
            seen_assets.add(content_id)
            merged_assets.append(content_id)

    content_el = ET.SubElement(out, q(ns_uri, "content"))

    # Keep other content children from representative (rare for category-menu slots),
    # but replace the content-assets list with merged assets.
    rep_content = rep.find(q(ns_uri, "content"))
    rep_other_children: List[ET.Element] = []
    if rep_content is not None:
        for child in list(rep_content):
            if child.tag.endswith("content-assets"):
                continue
            rep_other_children.append(copy.deepcopy(child))
    for child in rep_other_children:
        content_el.append(child)

    content_assets_el = ET.SubElement(content_el, q(ns_uri, "content-assets"))
    for content_id in merged_assets:
        asset = ET.SubElement(content_assets_el, q(ns_uri, "content-asset"))
        asset.set("content-id", content_id)

    # Custom attributes: keep all custom-attribute elements found in merged slots.
    # (Commerce import généralement accepte les doublons, et ça colle à l'exigence "mettre toutes".)
    custom_attrs_out: List[ET.Element] = []
    for c in candidates:
        ca_container = c.find(q(ns_uri, "custom-attributes"))
        if ca_container is None:
            continue
        for attr_el in ca_container.findall(q(ns_uri, "custom-attribute")):
            custom_attrs_out.append(copy.deepcopy(attr_el))

    if custom_attrs_out:
        custom_attrs_el = ET.SubElement(out, q(ns_uri, "custom-attributes"))
        for attr_el in custom_attrs_out:
            custom_attrs_el.append(attr_el)

    return out


def process_slot_file(input_path: Path, output_path: Path, template_text: str) -> None:
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns_uri = _ns_uri_from_tag(root.tag)
    # Keep the namespace as the default one (no `ns0:` prefix) to match typical SFCC exports.
    if ns_uri:
        ET.register_namespace("", ns_uri)

    # Gather candidates and groups
    candidates_by_key: Dict[Tuple[str, str], List[ET.Element]] = defaultdict(list)
    first_index_by_key: Dict[Tuple[str, str], int] = {}
    is_candidate_cache: Dict[ET.Element, bool] = {}

    children = list(root)
    for idx, el in enumerate(children):
        if el.tag != q(ns_uri, "slot-configuration"):
            continue
        slot_id = el.get("slot-id") or ""
        is_candidate = slot_id == "category-menu" or slot_id.startswith("category-menu-")
        is_candidate_cache[el] = is_candidate
        if not is_candidate:
            continue

        context_id = el.get("context-id")
        configuration_id = el.get("configuration-id")
        if not context_id or not configuration_id:
            raise ValueError(f"Candidate slot missing context-id/configuration-id: slot-id={slot_id}")

        key = (context_id, configuration_id)
        candidates_by_key[key].append(el)
        if key not in first_index_by_key:
            first_index_by_key[key] = idx

    # Pre-build merged slots per group
    merged_by_key: Dict[Tuple[str, str], ET.Element] = {}
    for key, candidates in candidates_by_key.items():
        merged_by_key[key] = merge_slot_group(ns_uri, key, candidates, template_text=template_text)

    # Rebuild children in original order:
    emitted = set()
    new_children: List[ET.Element] = []
    for el in children:
        if el.tag != q(ns_uri, "slot-configuration"):
            new_children.append(el)
            continue
        if not is_candidate_cache.get(el, False):
            new_children.append(el)
            continue

        key = (el.get("context-id"), el.get("configuration-id"))
        assert key in merged_by_key
        if key in emitted:
            continue
        new_children.append(merged_by_key[key])
        emitted.add(key)

    # Replace root children
    root[:] = new_children

    # Pretty print (Python 3.9+)
    try:
        ET.indent(tree, space="    ")
    except Exception:
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)


def run_batch(input_root: Path, output_root: Path, template_text: str) -> int:
    # Support both common names encountered in exports/imports.
    candidates = list(input_root.rglob("slot.xml")) + list(input_root.rglob("slots.xml"))
    # Remove duplicates while preserving discovery order.
    seen = set()
    slot_files: List[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        slot_files.append(path)

    if not slot_files:
        print(f"Aucun fichier slot.xml/slots.xml trouvé dans {input_root}")
        return 1

    for source_path in slot_files:
        relative_path = source_path.relative_to(input_root)
        destination_path = output_root / relative_path
        process_slot_file(source_path, destination_path, template_text)
        print(f"OK: {source_path} -> {destination_path}")

    print(f"Terminé: {len(slot_files)} fichier(s) traité(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Merge SFCC slot-configurations for category menus. "
            "Scanne un dossier d'entrée et écrit dans un dossier de sortie en conservant les chemins."
        )
    )
    parser.add_argument(
        "input_root",
        help="Répertoire racine d'entrée à scanner.",
    )
    parser.add_argument(
        "output_root",
        help="Répertoire racine de sortie.",
    )
    parser.add_argument(
        "--template",
        default="slots/content/megaMenu.ism",
        help="Template text to set on merged category-menu slots.",
    )
    args = parser.parse_args()

    return run_batch(Path(args.input_root), Path(args.output_root), args.template)


if __name__ == "__main__":
    raise SystemExit(main())

