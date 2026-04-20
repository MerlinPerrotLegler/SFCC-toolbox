import xml.etree.ElementTree as ET
import os
import sys
import copy
import fnmatch
import shutil
import re

try:
    import tty
    import termios
    _TTY_RAW = True
except ImportError:
    _TTY_RAW = False


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


def rm_url_aliases(fichier, rel):
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


def add_dev_wizard_custom_cartridge(fichier, rel):
    """In sites/**/site.xml add dev_wizard: at beginning of <custom-cartridges>."""
    try:
        tree, root, prefix = parse_xml(fichier)
        custom_cartridges = root.find(f'.//{prefix}custom-cartridges')
        if custom_cartridges is None:
            print(f"⏭️  [site] custom-cartridges introuvable : {rel}")
            return

        current = (custom_cartridges.text or '').strip()
        if not current:
            custom_cartridges.text = 'dev_wizard'
            tree.write(fichier, encoding="unicode", xml_declaration=True)
            print(f"✅ [site] dev_wizard ajouté : {rel}")
            return

        parts = [p.strip() for p in current.split(':') if p.strip()]
        if parts and parts[0] == 'dev_wizard':
            print(f"⏭️  [site] dev_wizard déjà en tête : {rel}")
            return

        parts = [p for p in parts if p != 'dev_wizard']
        custom_cartridges.text = 'dev_wizard:' + ':'.join(parts)
        tree.write(fichier, encoding="unicode", xml_declaration=True)
        print(f"✅ [site] dev_wizard préfixé : {rel}")
    except ET.ParseError as e:
        print(f"❌ Erreur de parsing : {rel} → {e}")


EXTERNAL_LOCATION_HTTP_FALLBACK = (
    'http://safety-staging.bollebrands.com/dw/image/v2/BFJW_STG/on/demandware.static/-/Sites-{catalog_id}/default/'
)
EXTERNAL_LOCATION_HTTPS_FALLBACK = (
    'https://safety-staging.bollebrands.com/dw/image/v2/BFJW_STG/on/demandware.static/-/Sites-{catalog_id}/default/'
)


def _build_external_url(existing_url, catalog_id, fallback_template):
    """Replace Sites-<catalog-id> in existing URL, or build a fallback URL."""
    if existing_url:
        pattern = re.compile(r'^(https?://.*/Sites-)([^/]+)(/.*)$')
        match = pattern.match(existing_url.strip())
        if match:
            return f'{match.group(1)}{catalog_id}{match.group(3)}'
    return fallback_template.format(catalog_id=catalog_id)


def configure_master_catalog_external_location(fichier, rel):
    """
    Configure <external-location> urls in master catalog header.
    Uses current catalog-id in Sites-<catalog-id> URL segment.
    """
    try:
        tree, root, prefix = parse_xml(fichier)

        if root.tag != f'{prefix}catalog':
            return

        catalog_id = (root.attrib.get('catalog-id') or '').strip()
        if not catalog_id or 'master-catalog' not in catalog_id:
            print(f"⏭️  [catalog] ignoré (pas un master catalog) : {rel}")
            return

        header = root.find(f'{prefix}header')
        if header is None:
            print(f"⏭️  [catalog] ignoré (header introuvable) : {rel}")
            return

        image_settings = header.find(f'{prefix}image-settings')
        if image_settings is None:
            image_settings = ET.SubElement(header, f'{prefix}image-settings')

        modifie = False

        internal_location = image_settings.find(f'{prefix}internal-location')
        if internal_location is not None:
            image_settings.remove(internal_location)
            modifie = True

        external_location = image_settings.find(f'{prefix}external-location')
        if external_location is None:
            external_location = ET.Element(f'{prefix}external-location')
            image_settings.insert(0, external_location)
            modifie = True
        else:
            children = list(image_settings)
            if children and children[0] is not external_location:
                image_settings.remove(external_location)
                image_settings.insert(0, external_location)
                modifie = True

        http_url = external_location.find(f'{prefix}http-url')
        if http_url is None:
            http_url = ET.SubElement(external_location, f'{prefix}http-url')
            modifie = True

        https_url = external_location.find(f'{prefix}https-url')
        if https_url is None:
            https_url = ET.SubElement(external_location, f'{prefix}https-url')
            modifie = True

        new_http = _build_external_url(http_url.text, catalog_id, EXTERNAL_LOCATION_HTTP_FALLBACK)
        new_https = _build_external_url(https_url.text, catalog_id, EXTERNAL_LOCATION_HTTPS_FALLBACK)

        if http_url.text == new_http and https_url.text == new_https and not modifie:
            print(f"⏭️  [catalog] external-location déjà conforme : {rel}")
            return

        http_url.text = new_http
        https_url.text = new_https
        tree.write(fichier, encoding="unicode", xml_declaration=True)
        print(f"✅ [catalog] external-location configuré : {rel}")
    except ET.ParseError as e:
        print(f"❌ Erreur de parsing : {rel} → {e}")


# --- Routing ---

def is_url_aliases_file(parts):
    """Vérifie si le fichier est sites/**/urls/aliases (fichier sans extension nommé 'aliases')."""
    return len(parts) >= 3 and parts[-1] == 'aliases' and parts[-2] == 'urls'


OPTION_KEYS = [
    'replace_dev_with_staging',
    'disable_all_jobs',
    'rm_allocation_timestamp_inventory_xml',
    'rm_cache_settings_for_developement',
    'rm_all_aliases',
    'configure_master_catalog_external_location',
    'prefix_dev_wizard_custom_cartridge',
]


def process_file(path, rel, options):
    """Apply transformations according to enabled options."""
    parts = rel.split('/')
    basename = parts[-1]
    in_sites = 'sites' in parts[:-1]
    in_inventory = 'inventory-lists' in parts[:-1]
    in_catalogs = 'catalogs' in parts[:-1]

    # 1. jobs.xml
    if basename == 'jobs.xml' and options.get('disable_all_jobs'):
        disable_all_jobs(path, rel)
        return

    # 2. sites/**/urls/aliases
    if is_url_aliases_file(parts) and options.get('rm_all_aliases'):
        rm_url_aliases(path, rel)
        return

    # 3. inventory-lists/inventory*.xml
    if in_inventory and fnmatch.fnmatch(basename, 'inventory*.xml') and options.get('rm_allocation_timestamp_inventory_xml'):
        rm_allocation_timestamp_inventory_xml(path, rel)
        return

    # 4. sites/**/cache-settings.xml
    if in_sites and basename == 'cache-settings.xml' and options.get('rm_cache_settings_for_developement'):
        rm_cache_settings_for_developement(path, rel)
        return

    # 5. catalogs/**/catalog.xml → configure external-location for master catalog
    if in_catalogs and basename == 'catalog.xml' and options.get('configure_master_catalog_external_location'):
        configure_master_catalog_external_location(path, rel)
        return

    # 6. sites/**/site.xml → prefix dev_wizard in custom-cartridges
    if in_sites and basename == 'site.xml' and options.get('prefix_dev_wizard_custom_cartridge'):
        add_dev_wizard_custom_cartridge(path, rel)
        return

    # 7. **/*.xml → replace dev by staging
    EXCLUDED_DIRS = {'custom-objects', 'pricebooks', 'customer-lists', 'libraries'}
    if options.get('replace_dev_with_staging') and basename.endswith('.xml') and not EXCLUDED_DIRS.intersection(parts[:-1]):
        replace_dev_with_staging(path, rel)


def get_key():
    """Read a single key (works with arrows, space, enter). Returns key name or char."""
    if _TTY_RAW and sys.stdin.isatty():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # ESC
                nxt = sys.stdin.read(2)
                if nxt == '[A':
                    return 'up'
                if nxt == '[B':
                    return 'down'
            elif ch == ' ':
                return 'space'
            elif ch in ('\r', '\n'):
                return 'enter'
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    else:
        line = sys.stdin.readline().strip()
        if line.lower() == 'enter' or line == '':
            return 'enter'
        if line == ' ':
            return 'space'
        if line in ('1', '2', '3', '4', '5', '6', '7'):
            return line
        return line or 'enter'


def run_tty_menu():
    """Show options menu; Space toggles selected, Up/Down move, Enter to run. Returns options dict."""
    labels = {
        'replace_dev_with_staging': 'a. replace_dev_with_staging',
        'disable_all_jobs': 'b. disable_all_jobs',
        'rm_allocation_timestamp_inventory_xml': 'c. rm_allocation_timestamp_inventory_xml',
        'rm_cache_settings_for_developement': 'd. rm_cache_settings_for_developement',
        'rm_all_aliases': 'e. rm_all_aliases',
        'configure_master_catalog_external_location': 'f. configure_master_catalog_external_location',
        'prefix_dev_wizard_custom_cartridge': 'g. prefix_dev_wizard_custom_cartridge',
    }
    options = {k: True for k in OPTION_KEYS}
    selected = 0

    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        print("Site Import STG → SB — Options (toggle with SPACE, ENTER to run)\n")
        for i, key in enumerate(OPTION_KEYS):
            mark = "[x]" if options[key] else "[ ]"
            cursor = " ► " if i == selected else "   "
            print(f"  {cursor} {mark} {labels[key]}")
        print("\n  SPACE: toggle  ↑/↓: move  ENTER: run")
        sys.stdout.flush()

        key = get_key()
        if key == 'enter':
            break
        if key == 'space':
            options[OPTION_KEYS[selected]] = not options[OPTION_KEYS[selected]]
        elif key == 'up':
            selected = (selected - 1) % len(OPTION_KEYS)
        elif key == 'down':
            selected = (selected + 1) % len(OPTION_KEYS)
        elif key in ('1', '2', '3', '4', '5', '6', '7'):
            idx = int(key) - 1
            options[OPTION_KEYS[idx]] = not options[OPTION_KEYS[idx]]

    return options


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


def parcourir_dossier(dossier, options):
    for racine, _, fichiers in os.walk(dossier):
        for fichier in fichiers:
            chemin = os.path.join(racine, fichier)
            rel = get_rel(chemin, dossier)
            process_file(chemin, rel, options)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python script.py <dossier>")
        sys.exit(1)

    dossier = os.path.abspath(sys.argv[1])

    if not os.path.isdir(dossier):
        print(f"❌ '{dossier}' n'est pas un dossier valide.")
        sys.exit(1)

    options = run_tty_menu()
    parcourir_dossier(dossier, options)
    print()
    clean_temp_files(dossier)
    print("\nTerminé.")
