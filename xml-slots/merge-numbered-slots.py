#!/usr/bin/env python3
"""
merge-numbered-slots.py

Fusionne les slots SFCC numérotés en un seul slot par groupe :
  - category-menu-right + category-menu-right-2/-3/-4  →  category-menu-right
  - collection-menu-item-1/-2/-3/...                   →  collection-menu-items

Pour chaque groupe (slot-de-base, context, context-id) :
  • Configuration par défaut  : tous les content-assets des positions par défaut
    (assigned-to-site=true), dans l'ordre des positions.
  • Configuration par campagne : pour chaque campagne qui touche au moins une
    position du groupe, les content-assets combinés (override campagne ou défaut
    pour les positions non overridées).

Source : PROD-camplaine-slots-catalog-storefront-mperrot
         (slots.xml avec slot-configuration-campaign-assignment + promotions.xml)

Sortie : outputs/merged-numbered-slots/ (même arborescence que la source)

Usage :
    python merge-numbered-slots.py <input_root> <output_root>
    python merge-numbered-slots.py \\
        inputs/PROD-camplaine-slots-catalog-storefront-mperrot \\
        outputs/merged-numbered-slots
"""

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Helpers XML
# ---------------------------------------------------------------------------

def _ns_uri(tag: str) -> str:
    if tag.startswith("{") and "}" in tag:
        return tag[1:].split("}", 1)[0]
    return ""


def q(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}" if ns else local


# ---------------------------------------------------------------------------
# Classification des slots numérotés
# ---------------------------------------------------------------------------

#  Retourne (group_key, target_slot_id, template, position) ou None
GroupInfo = Tuple[str, str, str, int]

SLOT_GROUPS = {
    "category-menu-right": ("category-menu-right", "slots/content/megaMenuNewTemplate.isml"),
    "collection-menu-item": ("collection-menu-items", "slots/content/megaMenuCollection.isml"),
}


def classify_numbered(slot_id: str) -> Optional[GroupInfo]:
    """
    Retourne (group_base, target_slot_id, template, position) si le slot est
    un variant numéroté, sinon None.

    Exemples :
        "category-menu-right"   → ("category-menu-right", "category-menu-right", tmpl, 1)
        "category-menu-right-3" → ("category-menu-right", "category-menu-right", tmpl, 3)
        "collection-menu-item-2"→ ("collection-menu-item", "collection-menu-items", tmpl, 2)
    """
    # category-menu-right (position 1)
    if slot_id == "category-menu-right":
        t, tmpl = SLOT_GROUPS["category-menu-right"]
        return ("category-menu-right", t, tmpl, 1)

    # category-menu-right-N
    m = re.fullmatch(r"category-menu-right-(\d+)", slot_id)
    if m:
        t, tmpl = SLOT_GROUPS["category-menu-right"]
        return ("category-menu-right", t, tmpl, int(m.group(1)))

    # collection-menu-item-N
    m = re.fullmatch(r"collection-menu-item-(\d+)", slot_id)
    if m:
        t, tmpl = SLOT_GROUPS["collection-menu-item"]
        return ("collection-menu-item", t, tmpl, int(m.group(1)))

    return None


# ---------------------------------------------------------------------------
# Extraction des content-assets d'une slot-configuration
# ---------------------------------------------------------------------------

def get_content_assets(el: ET.Element, ns: str) -> List[str]:
    """Retourne la liste ordonnée des content-id référencés dans <content-assets>."""
    ids: List[str] = []
    for ca in el.findall(f".//{q(ns, 'content-asset')}"):
        cid = ca.get("content-id")
        if cid:
            ids.append(cid)
    return ids


def get_enabled_flag(el: ET.Element, ns: str) -> str:
    ef = el.find(q(ns, "enabled-flag"))
    return ef.text.strip() if ef is not None and ef.text else "true"


# ---------------------------------------------------------------------------
# Construction d'une slot-configuration fusionnée
# ---------------------------------------------------------------------------

def build_merged_config(
    ns: str,
    target_slot_id: str,
    target_template: str,
    context: str,
    context_id: str,
    configuration_id: str,
    content_asset_ids: List[str],         # dans l'ordre des positions
    assigned_to_site: bool,
    default: bool,
    enabled: bool,
    source_comment: str,
) -> ET.Element:
    el = ET.Element(q(ns, "slot-configuration"))
    el.append(ET.Comment(f" {source_comment} "))
    el.set("slot-id", target_slot_id)
    el.set("context", context)
    el.set("context-id", context_id)
    el.set("configuration-id", configuration_id)
    if default:
        el.set("default", "true")
    el.set("assigned-to-site", "true" if assigned_to_site else "false")

    tmpl_el = ET.SubElement(el, q(ns, "template"))
    tmpl_el.text = target_template

    ef_el = ET.SubElement(el, q(ns, "enabled-flag"))
    ef_el.text = "true" if enabled else "false"

    content_el = ET.SubElement(el, q(ns, "content"))
    cas_el = ET.SubElement(content_el, q(ns, "content-assets"))
    for cid in content_asset_ids:
        ca_el = ET.SubElement(cas_el, q(ns, "content-asset"))
        ca_el.set("content-id", cid)

    return el


def _sanitize_config_id(s: str) -> str:
    """Remplace les caractères non SFCC-safe dans un configuration-id."""
    return re.sub(r"[^A-Za-z0-9_\-]", "-", s)


# ---------------------------------------------------------------------------
# Traitement d'un fichier slots.xml
# ---------------------------------------------------------------------------

def process_slots(input_path: Path, output_path: Path) -> None:
    tree = ET.parse(input_path)
    root = tree.getroot()
    ns = _ns_uri(root.tag)
    if ns:
        ET.register_namespace("", ns)

    TAG_CONFIG = q(ns, "slot-configuration")
    TAG_ASSIGN = q(ns, "slot-configuration-campaign-assignment")

    children = list(root)

    # -----------------------------------------------------------------------
    # 1. Séparer configurations et assignments ; identifier les slots numérotés
    # -----------------------------------------------------------------------
    configs: List[ET.Element] = []
    assignments: List[ET.Element] = []
    others: List[ET.Element] = []   # commentaires, etc.

    for el in children:
        if el.tag == TAG_CONFIG:
            configs.append(el)
        elif el.tag == TAG_ASSIGN:
            assignments.append(el)
        else:
            others.append(el)

    # -----------------------------------------------------------------------
    # 2. Identifier les groupes numérotés
    #    group_key = (group_base, context, context_id)
    #    On indexe chaque config par sa position
    # -----------------------------------------------------------------------
    # Pour savoir si une config "category-menu-right" position-1 appartient à
    # un groupe (i.e. il existe des positions 2+), on pré-calcule les context-id
    # qui ont au moins une position >= 2.
    numbered_contexts: Dict[Tuple[str, str, str], Set[int]] = defaultdict(set)
    # clé → (group_base, context, context_id)

    for el in configs:
        slot_id = el.get("slot-id", "")
        ctx = el.get("context", "")
        ctx_id = el.get("context-id", "")
        info = classify_numbered(slot_id)
        if info is None:
            continue
        group_base, target_slot, _, pos = info
        numbered_contexts[(group_base, ctx, ctx_id)].add(pos)

    # Un groupe est "réel" seulement s'il a au moins une position >= 2
    # (sinon category-menu-right seul n'est pas à fusionner)
    real_groups: Set[Tuple[str, str, str]] = {
        k for k, positions in numbered_contexts.items() if max(positions) >= 2
    }

    # Pour les collection-menu-item, on les fusionne dès qu'il y en a (même 1 seul)
    # car ils sont TOUJOURS des items d'une liste
    for k, positions in numbered_contexts.items():
        group_base, _, _ = k
        if group_base == "collection-menu-item":
            real_groups.add(k)

    # -----------------------------------------------------------------------
    # 3. Construire les structures de données par groupe
    #    positions_default[group_key][pos] = config_element
    #    positions_all[group_key][pos]     = list[config_elements] (tous, y compris campagnes)
    # -----------------------------------------------------------------------
    # Pour chaque groupe, pour chaque position :
    #   - default_config  : assigned-to-site=true  (peut être None)
    #   - extra_configs   : les autres (campagnes sur cette position)
    #
    PositionData = Dict[int, List[ET.Element]]
    group_all_configs: Dict[Tuple[str, str, str, str, str], PositionData] = defaultdict(
        lambda: defaultdict(list)
    )
    # Clé étendue : (group_base, target_slot, template, context, context_id)

    # Les configs non membres de groupes (à passer telles quelles)
    standalone_configs: List[ET.Element] = []

    for el in configs:
        slot_id = el.get("slot-id", "")
        ctx = el.get("context", "")
        ctx_id = el.get("context-id", "")
        info = classify_numbered(slot_id)
        if info is None:
            standalone_configs.append(el)
            continue
        group_base, target_slot, tmpl, pos = info
        gk = (group_base, ctx, ctx_id)
        if gk not in real_groups:
            # Pas un groupe réel → standalone
            standalone_configs.append(el)
            continue
        ek = (group_base, target_slot, tmpl, ctx, ctx_id)
        group_all_configs[ek][pos].append(el)

    # -----------------------------------------------------------------------
    # 4. Pour chaque groupe, trouver la config par défaut par position
    #    (assigned-to-site=true ; s'il y en a plusieurs, prendre la première)
    # -----------------------------------------------------------------------
    def default_config_for_pos(pos_configs: List[ET.Element]) -> Optional[ET.Element]:
        for el in pos_configs:
            if el.get("assigned-to-site") == "true":
                return el
        return None

    # -----------------------------------------------------------------------
    # 5. Traiter les assignments pour identifier les campagnes par groupe
    #    assign_by_group[(group_base, target_slot, tmpl, ctx, ctx_id)]
    #                   [campaign_id][position] = list[assignment_el]
    # -----------------------------------------------------------------------
    CampaignMap = Dict[str, Dict[int, List[ET.Element]]]
    assign_by_group: Dict[Tuple, CampaignMap] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    standalone_assignments: List[ET.Element] = []

    # Construire un mapping (config_id, slot_id, ctx, ctx_id) → position
    # pour retrouver rapidement la position d'un assignment
    config_key_to_pos: Dict[Tuple[str, str, str, str], Tuple[Tuple, int]] = {}
    for ek, pos_map in group_all_configs.items():
        for pos, el_list in pos_map.items():
            for el in el_list:
                cfg_id = el.get("configuration-id", "")
                slot_id = el.get("slot-id", "")
                ctx = el.get("context", "")
                ctx_id = el.get("context-id", "")
                config_key_to_pos[(cfg_id, slot_id, ctx, ctx_id)] = (ek, pos)

    for assign_el in assignments:
        slot_id = assign_el.get("slot-id", "")
        ctx = assign_el.get("context", "")
        ctx_id = assign_el.get("context-id", "")
        cfg_id = assign_el.get("configuration-id", "")
        campaign_id = assign_el.get("campaign-id", "")

        lookup = (cfg_id, slot_id, ctx, ctx_id)
        if lookup in config_key_to_pos:
            ek, pos = config_key_to_pos[lookup]
            assign_by_group[ek][campaign_id][pos].append(assign_el)
        else:
            standalone_assignments.append(assign_el)

    # -----------------------------------------------------------------------
    # 6. Générer les nouvelles configurations et assignments fusionnés
    # -----------------------------------------------------------------------
    new_configs: List[ET.Element] = []
    new_assignments: List[ET.Element] = []

    for ek, pos_map in group_all_configs.items():
        group_base, target_slot, tmpl, ctx, ctx_id = ek
        sorted_positions = sorted(pos_map.keys())

        # -- 6a. Configuration par défaut (assigned-to-site=true) ------------
        default_by_pos: Dict[int, ET.Element] = {}
        for pos in sorted_positions:
            dc = default_config_for_pos(pos_map[pos])
            if dc is not None:
                default_by_pos[pos] = dc

        if default_by_pos:
            # Prend la config de position 1 (ou la plus petite) comme base
            base_pos = min(default_by_pos.keys())
            base_el = default_by_pos[base_pos]
            base_cfg_id = base_el.get("configuration-id", f"merged-{ctx_id}-default")

            # Collecte tous les content-assets dans l'ordre des positions
            all_ca_ids: List[str] = []
            seen_ca: Set[str] = set()
            for pos in sorted_positions:
                dc = default_by_pos.get(pos)
                if dc is None:
                    continue
                for cid in get_content_assets(dc, ns):
                    if cid not in seen_ca:
                        all_ca_ids.append(cid)
                        seen_ca.add(cid)

            is_default = any(
                el.get("default") == "true" for el in default_by_pos.values()
            )
            is_enabled = any(
                get_enabled_flag(el, ns) == "true" for el in default_by_pos.values()
            )
            sources = ", ".join(
                f"pos{p}:{default_by_pos[p].get('configuration-id','')}"
                for p in sorted_positions
                if p in default_by_pos
            )

            merged_default = build_merged_config(
                ns=ns,
                target_slot_id=target_slot,
                target_template=tmpl,
                context=ctx,
                context_id=ctx_id,
                configuration_id=base_cfg_id,
                content_asset_ids=all_ca_ids,
                assigned_to_site=True,
                default=is_default,
                enabled=is_enabled,
                source_comment=f"fusionné depuis [{sources}]",
            )
            new_configs.append(merged_default)

        # -- 6b. Configurations de campagne ----------------------------------
        campaign_map = assign_by_group.get(ek, {})
        for campaign_id, pos_assign_map in campaign_map.items():
            # Positions affectées par cette campagne
            affected_positions = set(pos_assign_map.keys())

            # Content-assets dans l'ordre : override campagne ou défaut
            ca_ids: List[str] = []
            seen_ca_c: Set[str] = set()
            for pos in sorted_positions:
                # Trouver le content-asset pour cette position dans ce contexte de campagne
                if pos in pos_assign_map:
                    # Il y a un assignment pour cette position → trouver la config associée
                    assign_els = pos_assign_map[pos]
                    # Prendre le premier assignment pour récupérer la configuration
                    a = assign_els[0]
                    cfg_id_for_pos = a.get("configuration-id", "")
                    # Trouver la slot-configuration avec ce config-id pour cette position
                    matching = [
                        el for el in pos_map.get(pos, [])
                        if el.get("configuration-id") == cfg_id_for_pos
                    ]
                    if matching:
                        for cid in get_content_assets(matching[0], ns):
                            if cid not in seen_ca_c:
                                ca_ids.append(cid)
                                seen_ca_c.add(cid)
                        continue
                # Pas d'override → utiliser le défaut de cette position
                dc = default_by_pos.get(pos)
                if dc is not None:
                    for cid in get_content_assets(dc, ns):
                        if cid not in seen_ca_c:
                            ca_ids.append(cid)
                            seen_ca_c.add(cid)

            if not ca_ids:
                continue  # Rien à fusionner pour cette campagne

            # configuration-id : si la pos 1 a un assignment, réutiliser son config-id
            # (la config pos-1 devient la config fusionnée) ; sinon générer un nouvel id
            if 1 in pos_assign_map:
                a1 = pos_assign_map[1][0]
                merged_cfg_id = a1.get("configuration-id", "")
            else:
                safe_campaign = _sanitize_config_id(campaign_id)
                safe_ctx_id = _sanitize_config_id(ctx_id)
                merged_cfg_id = f"merged-{safe_ctx_id}--{safe_campaign}"

            # Commentaire source
            src_parts = []
            for pos in sorted_positions:
                if pos in pos_assign_map:
                    a = pos_assign_map[pos][0]
                    src_parts.append(
                        f"pos{pos}(campagne:{a.get('configuration-id','')})"
                    )
                elif pos in default_by_pos:
                    src_parts.append(
                        f"pos{pos}(defaut:{default_by_pos[pos].get('configuration-id','')})"
                    )

            merged_campaign_cfg = build_merged_config(
                ns=ns,
                target_slot_id=target_slot,
                target_template=tmpl,
                context=ctx,
                context_id=ctx_id,
                configuration_id=merged_cfg_id,
                content_asset_ids=ca_ids,
                assigned_to_site=False,
                default=False,
                enabled=True,
                source_comment=f"campagne {campaign_id} [{'; '.join(src_parts)}]",
            )
            new_configs.append(merged_campaign_cfg)

            # Nouveau assignment : utiliser le rank le plus élevé trouvé parmi les positions
            best_rank_el: Optional[ET.Element] = None
            best_rank_val = -1
            for pos_els in pos_assign_map.values():
                for a in pos_els:
                    rank_el = a.find(q(ns, "rank"))
                    if rank_el is not None and rank_el.text:
                        try:
                            v = int(rank_el.text.strip())
                            if v > best_rank_val:
                                best_rank_val = v
                                best_rank_el = rank_el
                        except ValueError:
                            pass

            new_assign = ET.Element(TAG_ASSIGN)
            new_assign.set("slot-id", target_slot)
            new_assign.set("context", ctx)
            new_assign.set("context-id", ctx_id)
            new_assign.set("configuration-id", merged_cfg_id)
            new_assign.set("campaign-id", campaign_id)
            if best_rank_el is not None:
                import copy
                new_assign.append(copy.deepcopy(best_rank_el))
            new_assignments.append(new_assign)

    # -----------------------------------------------------------------------
    # 7. Reconstruire le root
    #    On ne garde que les slots issus de la migration + leurs assignments.
    # -----------------------------------------------------------------------
    root.clear()

    for child in new_configs + new_assignments:
        root.append(child)

    try:
        ET.indent(tree, space="    ")
    except AttributeError:
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    print(f"OK: {input_path} → {output_path}")


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def run_batch(input_root: Path, output_root: Path) -> int:
    slots_files = list(input_root.rglob("slots.xml"))
    if not slots_files:
        print(f"Aucun slots.xml trouvé dans {input_root}")
        return 1

    for src in slots_files:
        rel = src.relative_to(input_root)
        dst = output_root / rel
        process_slots(src, dst)

    print(f"\nTerminé : {len(slots_files)} fichier(s) traité(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fusionne les slots numérotés SFCC (category-menu-right-N, collection-menu-item-N) "
            "en slots unifiés avec tous les content-assets regroupés."
        )
    )
    parser.add_argument("input_root", help="Répertoire racine d'entrée")
    parser.add_argument("output_root", help="Répertoire racine de sortie")
    args = parser.parse_args()
    return run_batch(Path(args.input_root), Path(args.output_root))


if __name__ == "__main__":
    raise SystemExit(main())
