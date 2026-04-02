#!/usr/bin/env python3

import argparse
import copy
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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


def custom_attribute_identity_key(attr_el: ET.Element) -> str:
    attr_id = attr_el.get("attribute-id", "")
    xml_lang = attr_el.get("{http://www.w3.org/XML/1998/namespace}lang", "")
    return f"{attr_id}::lang={xml_lang}"


def source_tag(slot_configuration: ET.Element) -> str:
    return (
        f"slot-id={slot_configuration.get('slot-id', '')}, "
        f"context-id={slot_configuration.get('context-id', '')}, "
        f"configuration-id={slot_configuration.get('configuration-id', '')}"
    )


def comment_safe(text: str) -> str:
    # XML comments must not contain the sequence --
    return text.replace("--", " - ")


def merge_slot_group(
    ns_uri: str,
    target_slot_id: str,
    context_id: str,
    configuration_id: str,
    candidates: List[ET.Element],
    template_text: str,
) -> ET.Element:
    rep = candidates[0]
    out = ET.Element(q(ns_uri, "slot-configuration"))

    slot_lineage = "; ".join(source_tag(c) for c in candidates)
    out.append(ET.Comment(f" slot fusionne, sources: {comment_safe(slot_lineage)} "))

    # slot attributes
    out.set("slot-id", target_slot_id)
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

    # Content: merge content-assets/content-asset content-id (order = first seen), track all sources per id
    merged_order: List[str] = []
    asset_sources: Dict[str, List[str]] = defaultdict(list)
    for c in candidates:
        src = source_tag(c)
        for asset_el in c.findall(f".//{q(ns_uri, 'content-assets')}/{q(ns_uri, 'content-asset')}"):
            content_id = asset_el.get("content-id")
            if not content_id:
                continue
            if content_id not in asset_sources:
                merged_order.append(content_id)
            if src not in asset_sources[content_id]:
                asset_sources[content_id].append(src)

    content_el = ET.SubElement(out, q(ns_uri, "content"))

    # slot.xsd defines <content> as a strict choice (products|categories|content-assets|html|recommended-products).
    # For merged category-menu slots we force content-assets only, otherwise having e.g. products + content-assets is invalid.
    content_assets_el = ET.SubElement(content_el, q(ns_uri, "content-assets"))
    for content_id in merged_order:
        asset = ET.SubElement(content_assets_el, q(ns_uri, "content-asset"))
        asset.set("content-id", content_id)
        lineage = "; ".join(asset_sources[content_id])
        content_assets_el.append(ET.Comment(f" origine: {comment_safe(lineage)} "))

    # Custom attributes: keep all custom-attribute elements found in merged slots.
    # (Commerce import généralement accepte les doublons, et ça colle à l'exigence "mettre toutes".)
    custom_attrs_out: List[Tuple[ET.Element, List[str]]] = []
    # Track distinct values per identity key (attribute-id + xml:lang).
    # Identical values are deduped, differing values are kept and flagged.
    attr_variants: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    attr_first_element: Dict[Tuple[str, str], ET.Element] = {}
    for c in candidates:
        ca_container = c.find(q(ns_uri, "custom-attributes"))
        if ca_container is None:
            continue
        for attr_el in ca_container.findall(q(ns_uri, "custom-attribute")):
            identity_key = custom_attribute_identity_key(attr_el)
            value_key = custom_attribute_dedupe_key(attr_el)
            source_info = source_tag(c)
            if value_key not in attr_variants[identity_key]:
                attr_variants[identity_key][value_key] = []
                attr_first_element[(identity_key, value_key)] = copy.deepcopy(attr_el)
            attr_variants[identity_key][value_key].append(source_info)

    conflict_comments: List[str] = []
    for identity_key, variants in attr_variants.items():
        # Keep exactly one element per unique value.
        for value_key in variants:
            sources_list = list(variants[value_key])
            custom_attrs_out.append(
                (copy.deepcopy(attr_first_element[(identity_key, value_key)]), sources_list)
            )

        if len(variants) > 1:
            details = []
            for idx, (value_key, sources) in enumerate(variants.items(), start=1):
                details.append(
                    f"variant#{idx} value-signature={value_key} sources=[{'; '.join(sources)}]"
                )
            conflict_line = f"CONFLICT custom-attribute {identity_key}: " + " | ".join(details)
            conflict_comments.append(conflict_line)
            print(
                f"WARNING {target_slot_id}/{context_id}/{configuration_id}: {conflict_line}"
            )

    if custom_attrs_out:
        custom_attrs_el = ET.SubElement(out, q(ns_uri, "custom-attributes"))
        for comment_text in conflict_comments:
            custom_attrs_el.append(ET.Comment(f" MANUAL_REVIEW {comment_safe(comment_text)} "))
        for attr_el, sources_list in custom_attrs_out:
            custom_attrs_el.append(attr_el)
            lineage = "; ".join(sources_list)
            custom_attrs_el.append(ET.Comment(f" origine: {comment_safe(lineage)} "))

    return out


def classify_slot(slot_id: str) -> Optional[Tuple[str, str]]:
    # (target slot-id, forced template)
    if slot_id == "category-menu-right" or slot_id.startswith("category-menu-right-"):
        return ("category-menu-right", "slots/content/megaMenuNewTemplate.isml")
    if slot_id == "collection-menu-items" or slot_id.startswith("collection-menu-item-"):
        return ("collection-menu-items", "slots/content/megaMenuCollection.isml")
    return None


def process_slot_file(input_path: Path, output_path: Path) -> None:
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns_uri = _ns_uri_from_tag(root.tag)
    # Keep the namespace as the default one (no `ns0:` prefix) to match typical SFCC exports.
    if ns_uri:
        ET.register_namespace("", ns_uri)

    # Gather candidates and groups: (target slot-id, template, context-id, configuration-id)
    candidates_by_key: Dict[Tuple[str, str, str, str], List[ET.Element]] = defaultdict(list)
    merge_key_by_el: Dict[ET.Element, Tuple[str, str, str, str]] = {}

    children = list(root)
    for idx, el in enumerate(children):
        if el.tag != q(ns_uri, "slot-configuration"):
            continue
        slot_id = el.get("slot-id") or ""
        slot_rule = classify_slot(slot_id)
        if slot_rule is None:
            continue

        context_id = el.get("context-id")
        configuration_id = el.get("configuration-id")
        if not context_id:
            raise ValueError(f"Candidate slot missing context-id: slot-id={slot_id}")
        if not configuration_id:
            raise ValueError(
                f"Candidate slot missing configuration-id: slot-id={slot_id}, context-id={context_id}"
            )

        target_slot_id, template_text = slot_rule
        key = (target_slot_id, template_text, context_id, configuration_id)
        candidates_by_key[key].append(el)
        merge_key_by_el[el] = key

    # Pre-build merged slots per group
    merged_by_key: Dict[Tuple[str, str, str, str], ET.Element] = {}
    for key, candidates in candidates_by_key.items():
        target_slot_id, group_template_text, context_id, configuration_id = key
        merged_by_key[key] = merge_slot_group(
            ns_uri,
            target_slot_id=target_slot_id,
            context_id=context_id,
            configuration_id=configuration_id,
            candidates=candidates,
            template_text=group_template_text,
        )

    # Rebuild children in original order:
    emitted = set()
    new_children: List[ET.Element] = []
    for el in children:
        if el.tag != q(ns_uri, "slot-configuration"):
            new_children.append(el)
            continue
        if el not in merge_key_by_el:
            new_children.append(el)
            continue

        key = merge_key_by_el[el]
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


def run_batch(input_root: Path, output_root: Path) -> int:
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
        process_slot_file(source_path, destination_path)
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
    args = parser.parse_args()

    return run_batch(Path(args.input_root), Path(args.output_root))


if __name__ == "__main__":
    raise SystemExit(main())

