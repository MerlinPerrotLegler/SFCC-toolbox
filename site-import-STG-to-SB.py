import xml.etree.ElementTree as ET
import os
import sys
import copy
import fnmatch
import shutil


def parse_xml(fichier):
    """Parse XML, enregistre le namespace par défaut, retourne (tree, root, prefix)."""
    tree = ET.parse(fichier)
    root = tree.getroot()
    ns = root.tag.split('}')[0].lstrip('{') if '}' in root.tag else ''
    if ns:
        ET.register_namespace('', ns)
    prefix = f'{{{ns}}}' if ns else ''
    return tree, root, prefix


def get_rel(path, base_dir):
    return os.path.relpath(path, base_dir).replace('\\', '/')


# --- Transformations ---

def replace_dev_with_staging(fichier, rel):
    """Copie le contenu de <staging> dans <development>."""
    try:
        tree, root, prefix = parse_xml(fichier)
        modifie = False

        def find_pairs(node):
            nonlocal modifie
            dev = node.find(f'{prefix}development')
            stag = node.find(f'{prefix}staging')
            if dev is not None and stag is not None:
                for child in list(dev):
                    dev.remove(child)
                dev.text = stag.text
                for child in stag:
                    dev.append(copy.deepcopy(child))
                modifie = True
            for child in node:
                find_pairs(child)

        find_pairs(root)

        if modifie:
            tree.write(fichier, encoding="unicode", xml_declaration=True)
            print(f"✅ [dev→staging] {rel}")
        else:
            print(f"⏭️  [dev→staging] ignoré (aucune balise trouvée) : {rel}")
    except ET.ParseError as e:
        print(f"❌ Erreur de parsing : {rel} → {e}")


def disable_all_jobs(fichier, rel):
    """Remplace run-recurring enabled=true par false."""
    try:
        with open(fichier, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content = content.replace(
            '<run-recurring enabled="true">',
            '<run-recurring enabled="false">'
        )
        if new_content != content:
            with open(fichier, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"✅ [jobs] run-recurring désactivé : {rel}")
        else:
            print(f"⏭️  [jobs] aucun run-recurring enabled=true trouvé : {rel}")
    except Exception as e:
        print(f"❌ Erreur : {rel} → {e}")


def fix_url_aliases(fichier, rel):
    """Remplace le fichier par un JSON vide {}."""
    try:
        with open(fichier, 'w', encoding='utf-8') as f:
            f.write('{}')
        print(f"✅ [aliases] remplacé par {{}} : {rel}")
    except Exception as e:
        print(f"❌ Erreur : {rel} → {e}")


def rm_allocation_timestamp_inventory_xml(fichier, rel):
    """Supprime les balises <allocation-timestamp>."""
    try:
        tree, root, prefix = parse_xml(fichier)
        tag = f'{prefix}allocation-timestamp'
        found = False

        for parent in root.iter():
            to_remove = [c for c in list(parent) if c.tag == tag]
            for child in to_remove:
                parent.remove(child)
                found = True

        if found:
            tree.write(fichier, encoding="unicode", xml_declaration=True)
            print(f"✅ [inventory] allocation-timestamp supprimé : {rel}")
        else:
            print(f"⏭️  [inventory] aucun allocation-timestamp trouvé : {rel}")
    except ET.ParseError as e:
        print(f"❌ Erreur de parsing : {rel} → {e}")


def rm_cache_settings_for_developement(fichier, rel):
    """Sous <development> : static-cache-ttl=0 et page-cache-enabled=false."""
    try:
        tree, root, prefix = parse_xml(fichier)
        modifie = False

        for dev in root.iter(f'{prefix}development'):
            for tag, val in [
                (f'{prefix}static-cache-ttl', '0'),
                (f'{prefix}page-cache-enabled', 'false'),
            ]:
                elem = dev.find(tag)
                if elem is not None:
                    elem.text = val
                    modifie = True

        if modifie:
            tree.write(fichier, encoding="unicode", xml_declaration=True)
            print(f"✅ [cache] paramètres de cache mis à jour : {rel}")
        else:
            print(f"⏭️  [cache] aucune balise trouvée : {rel}")
    except ET.ParseError as e:
        print(f"❌ Erreur de parsing : {rel} → {e}")


# --- Routing ---

def is_url_aliases_file(parts):
    """Vérifie si le fichier est sites/**/urls/aliases (fichier sans extension nommé 'aliases')."""
    return len(parts) >= 3 and parts[-1] == 'aliases' and parts[-2] == 'urls'


def process_file(path, rel):
    parts = rel.split('/')
    basename = parts[-1]
    in_sites = 'sites' in parts[:-1]
    in_inventory = 'inventory-lists' in parts[:-1]

    # 1. jobs.xml (n'importe où dans l'arborescence)
    if basename == 'jobs.xml':
        disable_all_jobs(path, rel)
        return

    # 2. sites/**/urls/aliases → JSON vide (fichier sans extension nommé 'aliases')
    if is_url_aliases_file(parts):
        fix_url_aliases(path, rel)
        return

    # 3. inventory-lists/inventory*.xml → supprime allocation-timestamp
    if in_inventory and fnmatch.fnmatch(basename, 'inventory*.xml'):
        rm_allocation_timestamp_inventory_xml(path, rel)
        return

    # 4. sites/**/cache-settings.xml → désactive le cache développement
    if in_sites and basename == 'cache-settings.xml':
        rm_cache_settings_for_developement(path, rel)
        return

    # 5. **/*.xml → remplace dev par staging (sauf dossiers exclus)
    EXCLUDED_DIRS = {'custom-objects', 'pricebooks', 'customer-lists', 'libraries'}
    if basename.endswith('.xml') and not EXCLUDED_DIRS.intersection(parts[:-1]):
        replace_dev_with_staging(path, rel)


MACOS_TEMP_DIR = '__MACOSX'
WINDOWS_TEMP_FILES = {'Thumbs.db', 'desktop.ini', 'ehthumbs.db', 'ehthumbs_vista.db'}


def clean_temp_files(dossier):
    """Supprime les fichiers temporaires macOS (._* et __MACOSX/) et Windows."""
    # Supprime les fichiers ._* et les fichiers Windows connus
    for racine, dirs, fichiers in os.walk(dossier, topdown=True):
        rel_racine = get_rel(racine, dossier)

        # Ignore (et supprimera) les dossiers __MACOSX
        if MACOS_TEMP_DIR in rel_racine.split('/'):
            continue

        for fichier in fichiers:
            chemin = os.path.join(racine, fichier)
            rel = get_rel(chemin, dossier)
            if fichier.startswith('._') or fichier in WINDOWS_TEMP_FILES:
                os.remove(chemin)
                print(f"🗑️  [temp] supprimé : {rel}")

        # Supprime les dossiers __MACOSX et leur contenu
        if MACOS_TEMP_DIR in dirs:
            chemin_macosx = os.path.join(racine, MACOS_TEMP_DIR)
            rel = get_rel(chemin_macosx, dossier)
            shutil.rmtree(chemin_macosx)
            dirs.remove(MACOS_TEMP_DIR)
            print(f"🗑️  [temp] supprimé : {rel}/")


def parcourir_dossier(dossier):
    for racine, _, fichiers in os.walk(dossier):
        for fichier in fichiers:
            chemin = os.path.join(racine, fichier)
            rel = get_rel(chemin, dossier)
            process_file(chemin, rel)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python script.py <dossier>")
        sys.exit(1)

    dossier = sys.argv[1]

    if not os.path.isdir(dossier):
        print(f"❌ '{dossier}' n'est pas un dossier valide.")
        sys.exit(1)

    parcourir_dossier(dossier)
    print()
    clean_temp_files(dossier)
    print("\nTerminé.")
