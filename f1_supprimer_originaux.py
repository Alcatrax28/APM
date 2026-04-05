import re
import curses
from pathlib import Path

from browser import browse_folder


VERSION_RE = re.compile(r"^(.+)_v(\d+)$", re.IGNORECASE)


def run(stdscr):
    # Étape 1 : sélection du dossier
    folder = browse_folder(stdscr)
    if folder is None:
        return

    # Étape 2 : analyse des fichiers
    to_delete, kept = _find_files_to_delete(folder)

    # Étape 3 : affichage et confirmation
    if not to_delete:
        _show_message(stdscr, folder, "Aucun fichier à supprimer trouvé.")
        return

    confirmed = _show_confirmation(stdscr, folder, to_delete, kept)

    # Étape 4 : suppression
    if confirmed:
        _do_delete(stdscr, to_delete)


# ---------------------------------------------------------------------------
# Logique d'analyse
# ---------------------------------------------------------------------------

def _find_files_to_delete(folder):
    """
    Pour chaque groupe (même nom de base + extension) :
      - S'il existe au moins une version _vN, on supprime :
          • l'original (sans suffixe)
          • toutes les versions sauf la plus haute
      - On garde : uniquement la version la plus haute (_vMax)

    Retourne (to_delete, kept) : deux listes de Path.
    """
    files = [f for f in Path(folder).iterdir() if f.is_file()]

    # Regroupement : clé = (base_stem, ext_lower)
    groups = {}
    for f in files:
        stem = f.stem
        ext = f.suffix.lower()
        m = VERSION_RE.match(stem)
        if m:
            base, v = m.group(1), int(m.group(2))
            key = (base, ext)
            groups.setdefault(key, {"original": None, "versions": {}})
            groups[key]["versions"][v] = f
        else:
            key = (stem, ext)
            groups.setdefault(key, {"original": None, "versions": {}})
            groups[key]["original"] = f

    to_delete = []
    kept = []

    for group in groups.values():
        if not group["versions"]:
            continue  # pas de version retouchée → on ne touche à rien

        max_v = max(group["versions"])

        if group["original"]:
            to_delete.append(group["original"])

        for v, path in group["versions"].items():
            if v == max_v:
                kept.append(path)
            else:
                to_delete.append(path)

    return (
        sorted(to_delete, key=lambda p: p.name.lower()),
        sorted(kept, key=lambda p: p.name.lower()),
    )


# ---------------------------------------------------------------------------
# Écrans curses
# ---------------------------------------------------------------------------

def _show_confirmation(stdscr, folder, to_delete, kept):
    offset = 0
    answer = None

    while answer is None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        visible = h - 12

        stdscr.addstr(0, 0, " F1 — Supprimer les originaux retouchés ".center(w), curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(2, 2, f"Dossier : {folder}", curses.A_DIM)
        stdscr.addstr(3, 2, "─" * (w - 4))

        stdscr.addstr(4, 2, f"Fichiers à supprimer  : ", curses.A_BOLD)
        stdscr.addstr(4, 26, str(len(to_delete)), curses.color_pair(1) if curses.has_colors() else curses.A_BOLD)

        stdscr.addstr(5, 2, f"Fichiers conservés    : ", curses.A_BOLD)
        stdscr.addstr(5, 26, str(len(kept)))

        stdscr.addstr(6, 2, "─" * (w - 4))

        # Liste scrollable des fichiers à supprimer
        count = len(to_delete)
        for i in range(visible):
            idx = offset + i
            if idx >= count:
                break
            name = to_delete[idx].name
            if len(name) > w - 8:
                name = name[: w - 11] + "..."
            stdscr.addstr(7 + i, 4, f"  {name}")

        if count > visible:
            scroll = f"[↑↓ défiler — {offset + 1}–{min(offset + visible, count)}/{count}]"
            stdscr.addstr(h - 5, w - len(scroll) - 2, scroll, curses.A_DIM)

        stdscr.addstr(h - 4, 2, "─" * (w - 4))
        stdscr.addstr(h - 3, 2, "Confirmer la suppression définitive ?", curses.A_BOLD)
        stdscr.addstr(h - 2, 2, "[O] Oui, supprimer      [N] Non, annuler", curses.A_DIM)
        stdscr.refresh()

        key = stdscr.getch()

        if key == curses.KEY_UP and offset > 0:
            offset -= 1
        elif key == curses.KEY_DOWN and offset + visible < count:
            offset += 1
        elif key in (ord("o"), ord("O")):
            answer = True
        elif key in (ord("n"), ord("N"), 27):
            answer = False

    return answer


def _do_delete(stdscr, to_delete):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    bar_w = w - 11  # largeur du contenu entre [ et ]

    stdscr.addstr(0, 0, " F1 — Suppression en cours... ".center(w), curses.A_BOLD | curses.A_REVERSE)
    stdscr.refresh()

    errors = []
    total = len(to_delete)

    for i, f in enumerate(to_delete, 1):
        try:
            f.unlink()
        except Exception as e:
            errors.append((f.name, str(e)))

        # Affichage après traitement du fichier
        pct = int(i / total * 100)
        filled = int(i / total * bar_w)
        name = f.name if len(f.name) <= w - 14 else f.name[:w - 17] + "..."
        stdscr.addstr(2, 2, f"Fichier : {name:<{w - 13}}")
        stdscr.addstr(3, 2, f"[{'█' * filled}{'░' * (bar_w - filled)}]  {pct:3d}%")
        stdscr.addstr(4, 2, f"{i} / {total} fichiers                    ")
        stdscr.refresh()

    stdscr.addstr(6, 2, "─" * (w - 4))
    ok = total - len(errors)
    stdscr.addstr(7, 2, f"{ok} fichier(s) supprimé(s) avec succès.", curses.A_BOLD)

    if errors:
        stdscr.addstr(8, 2, f"{len(errors)} erreur(s) :", curses.A_BOLD)
        for j, (name, err) in enumerate(errors[:h - 12]):
            stdscr.addstr(9 + j, 4, f"{name}: {err}")

    stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()


def _show_message(stdscr, folder, msg):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(0, 0, " F1 — Supprimer les originaux retouchés ".center(w), curses.A_BOLD | curses.A_REVERSE)
    stdscr.addstr(2, 2, f"Dossier : {folder}", curses.A_DIM)
    stdscr.addstr(4, 2, msg, curses.A_BOLD)
    stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()
