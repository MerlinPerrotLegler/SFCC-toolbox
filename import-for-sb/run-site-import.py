#!/usr/bin/env python3
"""
Site Import runner:
- select zip or folder in TTY browser (starts in inputs/)
- copy source to output/ keeping relative structure
- run site-import-STG-to-SB.py on copied output folder
- zip result as <name>-for-SB.zip
"""
import os
import sys
import zipfile
import tempfile
import shutil
import subprocess
import tty
import termios


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
INPUTS_ROOT = os.path.join(PROJECT_ROOT, "inputs")
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "outputs")
IMPORT_SCRIPT = os.path.join(SCRIPT_DIR, "site-import-STG-to-SB.py")


def get_base_name(path):
    """Return base name for output zip: filename without .zip, or folder name."""
    path = os.path.normpath(path)
    name = os.path.basename(path)
    if name.lower().endswith(".zip"):
        return name[:-4]
    return name


def _clear_screen():
    print("\033[2J\033[H", end="")


def _get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            nxt = sys.stdin.read(2)
            if nxt == '[A':
                return "up"
            if nxt == '[B':
                return "down"
            if nxt == '[C':
                return "right"
            if nxt == '[D':
                return "left"
            return "esc"
        if ch in ('\r', '\n'):
            return "enter"
        if ch.lower() == 'q':
            return "quit"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _list_entries(current_dir):
    entries = []
    with os.scandir(current_dir) as it:
        for e in it:
            if e.name.startswith('.'):
                continue
            if e.is_dir():
                entries.append((e.name, "dir"))
            elif e.is_file() and e.name.lower().endswith(".zip"):
                entries.append((e.name, "zip"))
    entries.sort(key=lambda item: (0 if item[1] == "dir" else 1, item[0].lower()))
    return entries


def select_path_tty(start_dir):
    """TTY browser with arrows; select zip or folder with Enter."""
    current_dir = os.path.abspath(start_dir)
    selected = 0

    while True:
        entries = _list_entries(current_dir)
        if entries and selected >= len(entries):
            selected = len(entries) - 1
        if selected < 0:
            selected = 0

        _clear_screen()
        print("Site Import — Sélection source")
        print(f"Dossier courant: {current_dir}\n")
        print("↑/↓: sélectionner  →: entrer dossier  ←: dossier parent")
        print("Entrée: choisir (dossier ou zip)  q: quitter\n")

        if not entries:
            print("  (Aucun dossier ni fichier .zip)")
        else:
            for i, (name, kind) in enumerate(entries):
                cursor = "►" if i == selected else " "
                icon = "📁" if kind == "dir" else "📦"
                print(f" {cursor} {icon} {name}")

        key = _get_key()
        if key == "quit":
            print("\nAnnulé.")
            sys.exit(0)
        if key == "up":
            selected -= 1
            continue
        if key == "down":
            selected += 1
            continue
        if key == "left":
            parent = os.path.dirname(current_dir)
            if parent and parent != current_dir:
                current_dir = parent
                selected = 0
            continue
        if key == "right":
            if not entries:
                continue
            name, kind = entries[selected]
            if kind == "dir":
                current_dir = os.path.join(current_dir, name)
                selected = 0
            continue
        if key == "enter":
            if not entries:
                continue
            name, _ = entries[selected]
            return os.path.join(current_dir, name)


def select_path():
    """Select source path via TTY browser, starting in inputs."""
    if not sys.stdin.isatty():
        print("TTY requis pour la sélection interactive.")
        sys.exit(1)
    if not os.path.isdir(INPUTS_ROOT):
        os.makedirs(INPUTS_ROOT, exist_ok=True)
    return select_path_tty(INPUTS_ROOT)


def unzip_to_temp(zip_path):
    """Unzip to a temp directory. Returns (temp_dir_path, should_cleanup)."""
    temp_dir = tempfile.mkdtemp(prefix="input-")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(temp_dir)
    return temp_dir, True


def get_site_folder(extracted_root):
    """If extracted_root has a single subdir, use it as site folder; else use root."""
    entries = [e for e in os.listdir(extracted_root) if not e.startswith(".")]
    if len(entries) == 1:
        single = os.path.join(extracted_root, entries[0])
        if os.path.isdir(single):
            return single
    return extracted_root


def run_import_script(site_folder):
    """Run input-STG-to-SB.py on site_folder (same process so TTY works)."""
    # Run in same Python so TTY menu works in this terminal
    result = subprocess.run(
        [sys.executable, IMPORT_SCRIPT, site_folder],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


def is_within(path, root):
    """Return True if path is within root."""
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(root)]) == os.path.abspath(root)
    except ValueError:
        return False


def get_output_folder(selected_path, is_zip):
    """Build destination folder in outputs while preserving relative layout from inputs when possible."""
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    if is_zip:
        if is_within(selected_path, INPUTS_ROOT):
            rel_zip = os.path.relpath(selected_path, INPUTS_ROOT)
            rel_no_ext = os.path.splitext(rel_zip)[0]
            return os.path.join(OUTPUT_ROOT, rel_no_ext)
        return os.path.join(OUTPUT_ROOT, get_base_name(selected_path))

    if is_within(selected_path, INPUTS_ROOT):
        rel = os.path.relpath(selected_path, INPUTS_ROOT)
        return os.path.join(OUTPUT_ROOT, rel)
    return os.path.join(OUTPUT_ROOT, os.path.basename(os.path.normpath(selected_path)))


def zip_folder(source_folder, output_zip_path):
    """Zip source_folder contents into output_zip_path (archive name = basename of source)."""
    base_name = os.path.basename(os.path.normpath(source_folder))
    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(source_folder):
            for f in files:
                path = os.path.join(root, f)
                arcname = os.path.join(base_name, os.path.relpath(path, source_folder))
                zf.write(path, arcname)


def main():
    path = select_path()
    is_zip = path.lower().endswith(".zip")
    base_name = get_base_name(path)

    if is_zip:
        work_dir, cleanup = unzip_to_temp(path)
        site_folder = get_site_folder(work_dir)
    else:
        site_folder = path
        work_dir = path
        cleanup = False

    site_folder = os.path.abspath(site_folder)
    output_site_folder = os.path.abspath(get_output_folder(path, is_zip))

    if os.path.exists(output_site_folder):
        shutil.rmtree(output_site_folder)
    shutil.copytree(site_folder, output_site_folder)

    print(f"\nSource (inchangé): {site_folder}")
    print(f"Copie de travail:   {output_site_folder}\n")
    run_import_script(output_site_folder)

    print("\n" + "=" * 60)
    print("Site folder path (check that everything is fine):")
    print(f"  {output_site_folder}")
    print("=" * 60)
    input("\nPress Enter to continue and create the -for-SB zip... ")

    output_dir = os.path.dirname(output_site_folder)
    output_zip = os.path.join(output_dir, base_name + "-for-SB.zip")

    print(f"\nCreating: {output_zip}")
    zip_folder(output_site_folder, output_zip)
    print(f"Done: {output_zip}")

    if cleanup:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
