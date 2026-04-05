import curses
from pathlib import Path


# ---------------------------------------------------------------------------
# Navigateur de DOSSIERS  (retourne un Path vers un dossier)
# ---------------------------------------------------------------------------

def browse_folder(stdscr):
    """
    Navigateur plein écran — dossiers uniquement.
    ESPACE = sélectionner le dossier courant | ENTRÉE = ouvrir | ← = remonter | ESC = annuler
    """
    return _browse(stdscr, mode="folder")


# ---------------------------------------------------------------------------
# Navigateur de FICHIERS  (retourne un Path vers un fichier)
# ---------------------------------------------------------------------------

def browse_file(stdscr, ext_filter=None, title="Sélectionner un fichier"):
    """
    Navigateur plein écran — dossiers + fichiers.
    ext_filter : ex. '.db'  pour n'afficher que les .db
    ENTRÉE sur un fichier = le sélectionner | ENTRÉE sur un dossier = l'ouvrir | ESC = annuler
    """
    return _browse(stdscr, mode="file", ext_filter=ext_filter, title=title)


# ---------------------------------------------------------------------------
# Implémentation commune
# ---------------------------------------------------------------------------

def _browse(stdscr, mode, ext_filter=None, title=None):
    current = Path.home()
    selected = 0
    offset = 0

    while True:
        entries = _get_entries(current, mode, ext_filter)
        h, w = stdscr.getmaxyx()
        visible = h - 7

        _draw(stdscr, h, w, current, entries, selected, offset, visible, mode, title)

        key = stdscr.getch()

        if key == curses.KEY_UP:
            if selected > 0:
                selected -= 1
                if selected < offset:
                    offset = selected

        elif key == curses.KEY_DOWN:
            if selected < len(entries) - 1:
                selected += 1
                if selected >= offset + visible:
                    offset = selected - visible + 1

        elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            if not entries:
                continue
            entry = entries[selected]
            if entry["is_dir"]:
                current = entry["path"]
                selected = 0
                offset = 0
            else:
                # Fichier sélectionné
                stdscr.clear()
                stdscr.refresh()
                return entry["path"]

        elif key in (curses.KEY_BACKSPACE, 127, 8):
            parent = current.parent
            if parent != current:
                current = parent
                selected = 0
                offset = 0

        elif key == ord(" ") and mode == "folder":
            stdscr.clear()
            stdscr.refresh()
            return current

        elif key == 27:  # ESC
            stdscr.clear()
            stdscr.refresh()
            return None


def _get_entries(path, mode, ext_filter):
    entries = []

    # Entrée parent
    if path.parent != path:
        entries.append({"path": path.parent, "name": ".. (dossier parent)", "is_dir": True})

    try:
        items = list(path.iterdir())
    except PermissionError:
        return entries

    dirs = sorted(
        [e for e in items if e.is_dir() and not e.name.startswith(".")],
        key=lambda e: e.name.lower(),
    )
    for d in dirs:
        entries.append({"path": d, "name": d.name + "/", "is_dir": True})

    if mode == "file":
        files = sorted(
            [
                e for e in items
                if e.is_file()
                and not e.name.startswith(".")
                and (ext_filter is None or e.suffix.lower() == ext_filter)
            ],
            key=lambda e: e.name.lower(),
        )
        for f in files:
            entries.append({"path": f, "name": f.name, "is_dir": False})

    return entries


def _draw(stdscr, h, w, current, entries, selected, offset, visible, mode, title):
    stdscr.erase()

    if title is None:
        title = " Navigateur de dossiers " if mode == "folder" else " Sélectionner un fichier "
    else:
        title = f" {title} "
    stdscr.addstr(0, max(0, (w - len(title)) // 2), title, curses.A_BOLD | curses.A_REVERSE)

    path_str = str(current)
    if len(path_str) > w - 22:
        path_str = "..." + path_str[-(w - 25):]
    stdscr.addstr(2, 2, f"Dossier courant : {path_str}", curses.A_DIM)
    stdscr.addstr(3, 2, "─" * (w - 4))

    if not entries:
        stdscr.addstr(5, 4, "(dossier vide ou inaccessible)")
    else:
        for i in range(visible):
            idx = offset + i
            if idx >= len(entries):
                break
            entry = entries[idx]
            y = 4 + i
            name = entry["name"]
            if len(name) > w - 6:
                name = name[: w - 9] + "..."
            attr = curses.A_REVERSE if idx == selected else curses.A_NORMAL
            # Dossiers en gras, fichiers normaux
            if entry["is_dir"] and idx != selected:
                attr |= curses.A_BOLD
            stdscr.addstr(y, 2, f" {name:<{w - 4}}", attr)

    count = len(entries)
    if count > visible:
        scroll_info = f"[{offset + 1}–{min(offset + visible, count)}/{count}]"
        stdscr.addstr(h - 3, w - len(scroll_info) - 2, scroll_info, curses.A_DIM)

    stdscr.addstr(h - 2, 2, "─" * (w - 4))
    if mode == "folder":
        hint = "ESPACE = Sélectionner ce dossier   ENTRÉE = Ouvrir   ← = Parent   ESC = Annuler"
    else:
        hint = "ENTRÉE = Sélectionner/Ouvrir   ← = Remonter   ESC = Annuler"
    stdscr.addstr(h - 1, max(0, (w - len(hint)) // 2), hint[: w - 1], curses.A_DIM)
    stdscr.refresh()
