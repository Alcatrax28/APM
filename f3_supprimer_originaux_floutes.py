import curses
from pathlib import Path

from browser import browse_folder


BLUR_PREFIX = "blur_"


def run(stdscr):
    # Étape 1 : sélection du dossier
    folder = browse_folder(stdscr)
    if folder is None:
        return

    # Étape 2 : analyse
    to_delete, kept = _find_files_to_delete(folder)

    if not to_delete:
        _show_message(stdscr, folder, "Aucun original flouté à supprimer trouvé.")
        return

    # Étape 3 : confirmation
    confirmed = _show_confirmation(stdscr, folder, to_delete, kept)

    # Étape 4 : suppression
    if confirmed:
        _do_delete(stdscr, to_delete)


# ---------------------------------------------------------------------------
# Logique d'analyse
# ---------------------------------------------------------------------------

def _find_files_to_delete(folder):
    """
    Pour chaque fichier blur_X présent dans le dossier :
      - Si X (l'original) existe aussi → X est à supprimer
      - blur_X est conservé

    Retourne (to_delete, kept) : deux listes de Path.
    """
    files = {f.name: f for f in Path(folder).iterdir() if f.is_file()}

    to_delete = []
    kept = []

    for name, blur_path in files.items():
        if not name.startswith(BLUR_PREFIX):
            continue
        original_name = name[len(BLUR_PREFIX):]
        if original_name in files:
            to_delete.append(files[original_name])
            kept.append(blur_path)

    return (
        sorted(to_delete, key=lambda p: p.name.lower()),
        sorted(kept,      key=lambda p: p.name.lower()),
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
        visible = h - 13

        stdscr.addstr(0, 0, " F3 — Supprimer les originaux floutés ".center(w), curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(2, 2, f"Dossier : {folder}", curses.A_DIM)
        stdscr.addstr(3, 2, "─" * (w - 4))

        stdscr.addstr(4, 2, "Fichiers à supprimer    : ", curses.A_BOLD)
        stdscr.addstr(4, 28, str(len(to_delete)), curses.color_pair(1) if curses.has_colors() else curses.A_BOLD)

        stdscr.addstr(5, 2, "Fichiers blur conservés : ", curses.A_BOLD)
        stdscr.addstr(5, 28, str(len(kept)))

        stdscr.addstr(6, 2, "─" * (w - 4))

        # Liste scrollable : original → blur conservé
        count = len(to_delete)
        for i in range(visible):
            idx = offset + i
            if idx >= count:
                break
            orig = to_delete[idx].name
            blur = kept[idx].name
            line = f"  {orig}  →  {blur}"
            if len(line) > w - 4:
                line = line[: w - 7] + "..."
            stdscr.addstr(7 + i, 2, line)

        if count > visible:
            scroll = f"[↑↓ défiler — {offset + 1}–{min(offset + visible, count)}/{count}]"
            stdscr.addstr(h - 5, w - len(scroll) - 2, scroll, curses.A_DIM)

        stdscr.addstr(h - 4, 2, "─" * (w - 4))
        stdscr.addstr(h - 3, 2, "Confirmer la suppression définitive des originaux ?", curses.A_BOLD)
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

    stdscr.addstr(0, 0, " F3 — Suppression en cours... ".center(w), curses.A_BOLD | curses.A_REVERSE)
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
    stdscr.addstr(0, 0, " F3 — Supprimer les originaux floutés ".center(w), curses.A_BOLD | curses.A_REVERSE)
    stdscr.addstr(2, 2, f"Dossier : {folder}", curses.A_DIM)
    stdscr.addstr(4, 2, msg, curses.A_BOLD)
    stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()
