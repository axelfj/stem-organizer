"""
Stem Organizer desktop app (Windows .exe / macOS .app).

Two buttons:
  * Install the FL Studio script into FL Studio's Hardware folder.
  * Check a folder of exported stems (same checks as stemcheck.py).

License: MIT (see LICENSE at the repository root).
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "stemcheck"))

import stemcheck  # noqa: E402

APP_NAME = "Stem Organizer"
SCRIPT_NAME = "device_StemOrganizer.py"
FL_SUBPATH = os.path.join("Image-Line", "FL Studio", "Settings", "Hardware", APP_NAME)


def resource_path(*parts):
    """Path to a bundled file, both from source and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", None) or os.path.join(HERE, "..")
    return os.path.join(base, *parts)


def documents_candidates(home=None, env=None):
    """Folders that may be the user's Documents, most likely first."""
    home = home or os.path.expanduser("~")
    env = os.environ if env is None else env
    found = []
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if env.get(key):
            found.append(os.path.join(env[key], "Documents"))
            found.append(os.path.join(env[key], "Documentos"))
    found.append(os.path.join(home, "Documents"))
    found.append(os.path.join(home, "Documentos"))
    seen, out = set(), []
    for p in found:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def find_fl_hardware_dir(home=None, env=None):
    """FL Studio's Settings/Hardware folder target, or None if FL's user data isn't found."""
    for docs in documents_candidates(home, env):
        if os.path.isdir(os.path.join(docs, "Image-Line", "FL Studio")):
            return os.path.join(docs, FL_SUBPATH)
    return None


def install_script(target_dir, source=None):
    source = source or resource_path("fl-studio", SCRIPT_NAME)
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, SCRIPT_NAME)
    shutil.copyfile(source, dest)
    return dest


NEXT_STEPS = (
    "Next, in FL Studio:\n"
    "1. OPTIONS > MIDI settings: enable any MIDI input and set its\n"
    "   Controller type to 'Stem Organizer'.\n"
    "2. VIEW > Script output > Stem Organizer > Interpreter tab.\n"
    "3. Type preview() to see the plan, organize() to apply it.\n"
    "4. Export WAV with 'Split mixer tracks' ticked."
)


def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext

    root = tk.Tk()
    root.title(APP_NAME)
    root.geometry("760x520")

    tk.Label(root, text=APP_NAME, font=("Helvetica", 18, "bold")).pack(pady=(14, 2))
    tk.Label(root, text="One sound, one track, one stem.").pack(pady=(0, 10))

    out = scrolledtext.ScrolledText(root, font=("Courier", 11), wrap="none")

    def show(text):
        out.configure(state="normal")
        out.delete("1.0", "end")
        out.insert("end", text)
        out.configure(state="disabled")

    def do_install():
        target = find_fl_hardware_dir()
        if target is None:
            messagebox.showinfo(
                APP_NAME, "FL Studio's user folder was not found.\n\nPick your "
                "'Image-Line/FL Studio/Settings/Hardware' folder.")
            picked = filedialog.askdirectory(title="FL Studio Settings/Hardware folder")
            if not picked:
                return
            target = os.path.join(picked, APP_NAME)
        try:
            dest = install_script(target)
        except OSError as e:
            messagebox.showerror(APP_NAME, "Could not install the script:\n%s" % e)
            return
        show("Installed:\n%s\n\nRestart FL Studio if it is open.\n\n%s" % (dest, NEXT_STEPS))

    def do_check():
        folder = filedialog.askdirectory(title="Folder with your exported stems")
        if not folder:
            return
        stems, problems = stemcheck.check_folder(folder)
        show(stemcheck.format_report(folder, stems, problems))

    buttons = tk.Frame(root)
    buttons.pack(pady=4)
    tk.Button(buttons, text="Install FL Studio script", width=24,
              command=do_install).pack(side="left", padx=8)
    tk.Button(buttons, text="Check a stems folder...", width=24,
              command=do_check).pack(side="left", padx=8)
    out.pack(fill="both", expand=True, padx=12, pady=12)
    show("1. Install the FL Studio script, then organize your project in FL.\n"
         "2. Export your stems and check the folder here before sending it.")
    root.mainloop()


def selftest():
    """Used by CI on the built app: checks the bundle without opening a window."""
    import tkinter  # noqa: F401
    import numpy  # noqa: F401
    with open(resource_path("fl-studio", SCRIPT_NAME)) as f:
        assert "# name=Stem Organizer" in f.read()
    stems, problems = stemcheck.check_folder(HERE)
    assert problems and problems[0]["level"] == "error"
    print("selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        run_gui()
