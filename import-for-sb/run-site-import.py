#!/usr/bin/env python3
"""
Site Import runner: select zip or folder → unzip if needed → run site-import-STG-to-SB.py
→ pause with path → zip result as <name>-for-SB.zip
"""
import os
import sys
import zipfile
import tempfile
import shutil
import subprocess

try:
    import tkinter as tk
    from tkinter import filedialog
    from tkinter import font as tkfont
    _HAS_TK = True
except ImportError:
    _HAS_TK = False


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMPORT_SCRIPT = os.path.join(SCRIPT_DIR, "site-import-STG-to-SB.py")


def get_base_name(path):
    """Return base name for output zip: filename without .zip, or folder name."""
    path = os.path.normpath(path)
    name = os.path.basename(path)
    if name.lower().endswith(".zip"):
        return name[:-4]
    return name


def _select_via_gui():
    """Show native-style dialog: two buttons to pick ZIP or folder. Returns path or None."""
    chosen = [None]  # mutable so inner callback can set it

    root = tk.Tk()
    root.withdraw()
    root.title("Site Import")

    panel = tk.Toplevel(root)
    panel.title("Site Import — Choose source")
    panel.resizable(False, False)
    panel.attributes("-topmost", True)
    panel.configure(bg="#f5f5f5", padx=0, pady=0)

    pad = 28
    w, h = 340, 200
    panel.geometry(f"{w}x{h}")
    panel.update_idletasks()
    x = (panel.winfo_screenwidth() - w) // 2
    y = max(0, (panel.winfo_screenheight() - h) // 2 - 40)
    panel.geometry(f"+{x}+{y}")

    tk.Label(
        panel,
        text="Select a site export to prepare for Sandbox",
        font=("Helvetica", 11),
        fg="#333",
        bg="#f5f5f5",
    ).pack(pady=(pad, 14))

    def on_zip():
        path = filedialog.askopenfilename(
            parent=panel,
            title="Select ZIP file",
            filetypes=[("ZIP archives", "*.zip"), ("All files", "*.*")],
        )
        if path:
            chosen[0] = path
        panel.destroy()
        root.destroy()

    def on_folder():
        path = filedialog.askdirectory(parent=panel, title="Select site folder")
        if path:
            chosen[0] = path
        panel.destroy()
        root.destroy()

    btn_font = tkfont.Font(family="Helvetica", size=11, weight="bold")
    frame = tk.Frame(panel, padx=pad, pady=8, bg="#f5f5f5")
    frame.pack(fill="x", expand=True)

    zip_btn = tk.Button(
        frame,
        text="📦  ZIP file",
        font=btn_font,
        width=14,
        height=2,
        cursor="hand2",
        command=on_zip,
        bg="#d4ebf7",
        activebackground="#b8dff2",
        fg="#1a5276",
        relief="flat",
        borderwidth=0,
    )
    zip_btn.pack(side="left", padx=(0, 10))

    folder_btn = tk.Button(
        frame,
        text="📁  Folder",
        font=btn_font,
        width=14,
        height=2,
        cursor="hand2",
        command=on_folder,
        bg="#d5f5e3",
        activebackground="#abebc6",
        fg="#186a3b",
        relief="flat",
        borderwidth=0,
    )
    folder_btn.pack(side="left")

    panel.protocol("WM_DELETE_WINDOW", lambda: (panel.destroy(), root.destroy()))
    panel.focus_force()
    root.mainloop()
    return chosen[0]


def select_path():
    """Let user pick a zip file or folder via GUI, or fallback to terminal input."""
    if _HAS_TK:
        path = _select_via_gui()
        if path:
            return os.path.abspath(path)
        print("No file or folder selected. Exiting.")
        sys.exit(0)
    # Fallback: terminal prompt
    print("Site Import: select a ZIP file or a folder containing the site.\n")
    while True:
        path = input("Path to ZIP or folder: ").strip()
        if not path:
            continue
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        if os.path.isfile(path):
            if path.lower().endswith(".zip"):
                return path
            print("Not a .zip file. Enter a .zip or a folder path.\n")
        elif os.path.isdir(path):
            return path
        else:
            print("Path not found. Try again.\n")


def unzip_to_temp(zip_path):
    """Unzip to a temp directory. Returns (temp_dir_path, should_cleanup)."""
    temp_dir = tempfile.mkdtemp(prefix="site-import-")
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
    """Run site-import-STG-to-SB.py on site_folder (same process so TTY works)."""
    # Run in same Python so TTY menu works in this terminal
    result = subprocess.run(
        [sys.executable, IMPORT_SCRIPT, site_folder],
        cwd=SCRIPT_DIR,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)


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
    print(f"\nRunning site-import on: {site_folder}\n")
    run_import_script(site_folder)

    print("\n" + "=" * 60)
    print("Site folder path (check that everything is fine):")
    print(f"  {site_folder}")
    print("=" * 60)
    input("\nPress Enter to continue and create the -for-SB zip... ")

    # Output zip: same directory as selection, name = base_name + "-for-SB.zip"
    if is_zip:
        output_dir = os.path.dirname(path)
    else:
        output_dir = os.path.dirname(path)
    output_zip = os.path.join(output_dir, base_name + "-for-SB.zip")

    print(f"\nCreating: {output_zip}")
    zip_folder(site_folder, output_zip)
    print(f"Done: {output_zip}")

    if cleanup:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
