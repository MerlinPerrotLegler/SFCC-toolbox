#!/usr/bin/env python3
"""
D2C-1326 : à partir d’un export library SFCC (XML), génère un NOUveau fichier
contenant uniquement l’en-tête <library> et les content assets listés dans
REPLACEMENTS (clés), sans les autres <content>. Aucun <folder> n’est copié.

Les entrées dont la valeur est "Removed" ne sont pas exportées (ex. Section3-2).

Ensuite les remplacements de chaînes REPLACEMENTS sont appliqués sur chaque
bloc <content> écrit (comme l’ancien parcours de fichiers).

Usage :
  python3 "Migration with D2C-1326.py" \\
    -i STG-BolleSafetyEUSharedLibrary-20260504.xml \\
    -o migration-D2C-1326-subset.xml
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET

LIB_NS = "http://www.demandware.com/xml/impex/library/2006-10-31"

REPLACEMENTS = {
    "RXPrescription-Section0-1": "RXPrescription-VoucherEntry-1",
    "RXPrescription-Section0-2": "RXPrescription-VoucherEntry-2",
    "RXPrescription-Section1-1": "RXPrescription-PupillaryDistance-1",
    "RXPrescription-Section1-2": "RXPrescription-PupillaryDistance-2",
    "RXPrescription-Section2-1": "RXPrescription-FrameSelector-1",
    "RXPrescription-Section2-2": "RXPrescription-FrameSelector-2",
    "RXPrescription-Section3-1": "RXPrescription-Lens-Title",
    "RXPrescription-Section3-2": "Removed",
    "RXPrescription-Section3-Prescription-1": "RXPrescription-Prescription-Title",
    "RXPrescription-Section3-Prescription-progressive": "RXPrescription-PrescriptionType-progressive",
    "RXPrescription-Section3-Prescription-single-vision": "RXPrescription-PrescriptionType-single-vision",
    "RXPrescription-Section3-Lens-indoor": "RXPrescription-LensType-indoor",
    "RXPrescription-Section3-Lens-indoor-outdoor": "RXPrescription-LensType-indoor-outdoor",
    "RXPrescription-Section3-Lens-outdoor": "RXPrescription-LensType-outdoor",
    "RXPrescription-Section3-Lens-indoor-ar": "RXPrescription-LensType-indoor-ar",
    "RXPrescription-Section3-Lens-outdoor-ar": "RXPrescription-LensType-outdoor-ar",
    "RXPrescription-Section4-1": "RXPrescription-Form-1",
    "RXPrescription-Section4-2": "RXPrescription-Form-2",
    "RXPrescription-Section5-1": "RXPrescription-Summary-1",
    "RXPrescription-Section5-2": "RXPrescription-Summary-2",
}


def _keep_content_ids() -> set[str]:
    return {old for old, new in REPLACEMENTS.items() if new != "Removed"}


def q(local: str) -> str:
    return f"{{{LIB_NS}}}{local}"


def escape_attr_val(val: str) -> str:
    return (
        val.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def library_opening_tag(attrib: dict[str, str]) -> str:
    parts = [f'xmlns="{LIB_NS}"']
    for k, v in attrib.items():
        parts.append(f'{k}="{escape_attr_val(str(v))}"')
    return "<library " + " ".join(parts) + ">\n"


def apply_replacements(fragment: str) -> str:
    out = fragment
    for old, new in REPLACEMENTS.items():
        out = out.replace(old, new)
    return out


def strip_etree_namespace_prefix(fragment: str) -> str:
    """ElementTree sérialise avec préfixe (ex. ns0:) ; le défaut SFCC est sans préfixe sous <library>."""
    m = re.search(
        r' xmlns:([^\s=]+)="' + re.escape(LIB_NS) + r'"',
        fragment,
    )
    if not m:
        return fragment
    prefix = m.group(1)
    fragment = fragment.replace(f' xmlns:{prefix}="{LIB_NS}"', "", 1)
    return fragment.replace(f"{prefix}:", "")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export partiel library SFCC (D2C-1326) : header + content assets listés."
    )
    parser.add_argument("-i", "--input", required=True, help="XML bibliothèque source")
    parser.add_argument("-o", "--output", required=True, help="Nouveau XML (sans écraser la source)")
    args = parser.parse_args()

    keep = _keep_content_ids()
    q_folder = q("folder")
    q_content = q("content")
    q_library = q("library")

    found: set[str] = set()
    library_started = False

    with open(args.input, "rb") as inf, open(args.output, "wb") as outf:
        outf.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')

        for event, elem in ET.iterparse(inf, events=("start", "end")):
            if event == "start" and elem.tag == q_library:
                outf.write(library_opening_tag(dict(elem.attrib)).encode("utf-8"))
                library_started = True
                continue

            if event != "end":
                continue

            if elem.tag == q_folder:
                elem.clear()

            elif elem.tag == q_content:
                cid = elem.get("content-id")
                if cid in keep:
                    found.add(cid)
                    chunk = ET.tostring(
                        elem, encoding="utf-8", xml_declaration=False
                    ).decode("utf-8")
                    chunk = strip_etree_namespace_prefix(chunk)
                    outf.write(apply_replacements(chunk).encode("utf-8"))
                    outf.write(b"\n")
                elem.clear()

        if not library_started:
            sys.exit("Erreur : balise <library> introuvable dans le fichier source.")

        outf.write(b"</library>\n")

    missing = keep - found
    if missing:
        print(
            f"Avertissement : {len(missing)} content-id attendu(s) absent(s) du source :",
            file=sys.stderr,
        )
        for mid in sorted(missing):
            print(f"  - {mid}", file=sys.stderr)

    print(
        f"Écrit {len(found)} content asset(s) dans {args.output}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
