import re
import curses
import sqlite3
from pathlib import Path

from browser import browse_folder, browse_file


# ---------------------------------------------------------------------------
# Requête DigiKam (même logique que le script .sh)
# ---------------------------------------------------------------------------

DIGIKAM_QUERY = """
    SELECT
        Images.name,
        Tags.name,
        ImageTagProperties.value
    FROM ImageTagProperties
    JOIN ImageTags ON ImageTagProperties.imageid = ImageTags.imageid
    JOIN Tags      ON ImageTags.tagid = Tags.id
    JOIN Images    ON Images.id = ImageTags.imageid
    WHERE ImageTagProperties.property = 'tagRegion'
"""

RECT_FIELDS = {
    "x": re.compile(r'x="(\d+)"'),
    "y": re.compile(r'y="(\d+)"'),
    "w": re.compile(r'width="(\d+)"'),
    "h": re.compile(r'height="(\d+)"'),
}


# ---------------------------------------------------------------------------
# Point d'entrée F2
# ---------------------------------------------------------------------------

def run(stdscr):
    # 1. Sélection de la base DigiKam
    db_path = browse_file(
        stdscr,
        ext_filter=".db",
        title="Sélectionner digikam4.db",
    )
    if db_path is None:
        return

    # 2. Saisie du/des nom(s) de personne (regex accepté)
    target = _input_text(
        stdscr,
        title="F2 — Flouter des visages",
        prompt="Nom(s) à flouter (regex accepté, ex : Alice|Bob) :",
    )
    if not target:
        return

    # 3. Sélection du dossier racine des images
    base_dir = browse_folder(stdscr)
    if base_dir is None:
        return

    # 4. Extraction des régions depuis la DB
    try:
        faces = _query_digikam(db_path, target)
    except Exception as e:
        _show_message(stdscr, f"Erreur base de données : {e}")
        return

    if not faces:
        _show_message(stdscr, f"Aucun visage trouvé pour : {target}")
        return

    # 5. Résolution des chemins réels
    jobs = _resolve_files(faces, base_dir)

    not_found = [name for name in faces if not any(
        p.name == name for p in jobs
    )]

    if not jobs:
        _show_message(stdscr, "Aucun fichier correspondant trouvé dans le dossier sélectionné.")
        return

    # 6. Confirmation avec compteur
    confirmed = _show_confirmation(stdscr, jobs, not_found, target, db_path, base_dir)

    # 7. Floutage
    if confirmed:
        _do_blur(stdscr, jobs)


# ---------------------------------------------------------------------------
# Logique DigiKam
# ---------------------------------------------------------------------------

def _query_digikam(db_path, target_regex):
    """
    Retourne dict { filename: [(x, y, w, h), ...] }
    Même filtrage regex que le script bash : re.search(target, tagname)
    """
    faces = {}
    con = sqlite3.connect(str(db_path))
    try:
        for filename, tagname, rect_xml in con.execute(DIGIKAM_QUERY):
            if not re.search(target_regex, tagname, re.IGNORECASE):
                continue
            rect = _parse_rect(rect_xml)
            if rect is None:
                continue
            faces.setdefault(filename, []).append(rect)
    finally:
        con.close()
    return faces


def _parse_rect(value):
    """Extrait (x, y, w, h) depuis le XML DigiKam. Retourne None si invalide."""
    try:
        return (
            int(RECT_FIELDS["x"].search(value).group(1)),
            int(RECT_FIELDS["y"].search(value).group(1)),
            int(RECT_FIELDS["w"].search(value).group(1)),
            int(RECT_FIELDS["h"].search(value).group(1)),
        )
    except (AttributeError, ValueError):
        return None


def _resolve_files(faces, base_dir):
    """
    Recherche récursive dans base_dir (même logique que `find BASE_DIR -name FILE | head -n 1`).
    Retourne dict { Path(image): [(x, y, w, h), ...] }
    """
    # Construit un index nom → chemin (premier trouvé = prioritaire, comme head -n 1)
    index = {}
    for path in Path(base_dir).rglob("*"):
        if path.is_file() and path.name not in index:
            index[path.name] = path

    return {index[name]: rects for name, rects in faces.items() if name in index}


# ---------------------------------------------------------------------------
# Floutage Pillow (équivalent de `magick ... -gaussian-blur 0x20`)
# ---------------------------------------------------------------------------

def _blur_image(src_path, jobs_rects):
    """
    Floute les régions de visage sur src_path.
    Sauvegarde sous blur_[filename] dans le même dossier.
    Retourne le chemin de sortie.
    """
    from PIL import Image, ImageFilter

    img = Image.open(src_path)
    iw, ih = img.size

    for (x, y, w, h) in jobs_rects:
        # Clamp aux dimensions de l'image
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(iw, x + w), min(ih, y + h)
        if x2 <= x1 or y2 <= y1:
            continue

        region = img.crop((x1, y1, x2, y2))
        # Double passe de flou fort (~équivalent gaussian-blur 0x20 d'ImageMagick)
        blurred = region.filter(ImageFilter.GaussianBlur(radius=25))
        blurred = blurred.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(blurred, (x1, y1))

    out_path = src_path.parent / f"blur_{src_path.name}"
    img.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# Écrans curses
# ---------------------------------------------------------------------------

def _input_text(stdscr, title, prompt):
    """Saisie de texte simple avec support Unicode (accents, etc.)."""
    curses.curs_set(1)
    text = ""

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()

        stdscr.addstr(0, 0, f" {title} ".center(w), curses.A_BOLD | curses.A_REVERSE)
        stdscr.addstr(3, 2, prompt)
        stdscr.addstr(4, 2, "─" * (w - 4))

        # Champ de saisie
        display = text[-(w - 6):] if len(text) > w - 6 else text
        stdscr.addstr(5, 2, f"> {display:<{w - 5}}")
        stdscr.move(5, 4 + len(display))

        stdscr.addstr(h - 2, 2, "ENTRÉE = Valider   ESC = Annuler", curses.A_DIM)
        stdscr.refresh()

        key = stdscr.get_wch()

        if isinstance(key, str):
            if key in ("\n", "\r"):
                break
            elif key == "\x1b":
                curses.curs_set(0)
                return None
            else:
                text += key
        else:
            if key in (curses.KEY_ENTER,):
                break
            elif key == 27:
                curses.curs_set(0)
                return None
            elif key in (curses.KEY_BACKSPACE, 127, 8):
                text = text[:-1]

    curses.curs_set(0)
    return text.strip() or None


def _show_confirmation(stdscr, jobs, not_found, target, db_path, base_dir):
    """
    Affiche le récapitulatif et demande confirmation.
    jobs      : dict { Path: [(x,y,w,h),...] }
    not_found : liste de noms de fichiers introuvables
    """
    file_list = sorted(jobs.keys(), key=lambda p: p.name.lower())
    total_faces = sum(len(v) for v in jobs.values())
    offset = 0
    answer = None

    while answer is None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        visible = h - 15

        stdscr.addstr(0, 0, " F2 — Flouter des visages ".center(w), curses.A_BOLD | curses.A_REVERSE)

        stdscr.addstr(2, 2, f"Base DigiKam : {db_path}", curses.A_DIM)
        stdscr.addstr(3, 2, f"Dossier      : {base_dir}", curses.A_DIM)
        stdscr.addstr(4, 2, f"Filtre       : {target}", curses.A_DIM)
        stdscr.addstr(5, 2, "─" * (w - 4))

        stdscr.addstr(6, 2, "Images à traiter  : ", curses.A_BOLD)
        stdscr.addstr(6, 22, str(len(file_list)), curses.A_BOLD)

        stdscr.addstr(7, 2, "Visages détectés  : ", curses.A_BOLD)
        stdscr.addstr(7, 22, str(total_faces))

        if not_found:
            stdscr.addstr(8, 2, f"Fichiers introuvables : {len(not_found)}", curses.A_DIM)

        stdscr.addstr(9, 2, "─" * (w - 4))

        # Liste scrollable des fichiers
        count = len(file_list)
        for i in range(visible):
            idx = offset + i
            if idx >= count:
                break
            p = file_list[idx]
            n_faces = len(jobs[p])
            line = f"  {p.name}  ({n_faces} visage{'s' if n_faces > 1 else ''})"
            if len(line) > w - 4:
                line = line[: w - 7] + "..."
            stdscr.addstr(10 + i, 2, line)

        if count > visible:
            scroll = f"[↑↓ défiler — {offset + 1}–{min(offset + visible, count)}/{count}]"
            stdscr.addstr(h - 5, w - len(scroll) - 2, scroll, curses.A_DIM)

        stdscr.addstr(h - 4, 2, "─" * (w - 4))
        stdscr.addstr(h - 3, 2, "Les images floutées seront sauvegardées sous  blur_[nom_fichier]", curses.A_DIM)
        stdscr.addstr(h - 2, 2, "Lancer le floutage ?   [O] Oui      [N] Non / Annuler", curses.A_BOLD)
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


def _do_blur(stdscr, jobs):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    bar_w = w - 11  # largeur du contenu entre [ et ]

    stdscr.addstr(0, 0, " F2 — Floutage en cours... ".center(w), curses.A_BOLD | curses.A_REVERSE)
    stdscr.refresh()

    file_list = sorted(jobs.keys(), key=lambda p: p.name.lower())
    total = len(file_list)
    errors = []

    for i, src in enumerate(file_list, 1):
        # Affichage avant traitement (nom du fichier en cours)
        name = src.name if len(src.name) <= w - 14 else src.name[:w - 17] + "..."
        stdscr.addstr(2, 2, f"Fichier : {name:<{w - 13}}")
        pct_before = int((i - 1) / total * 100)
        filled_before = int((i - 1) / total * bar_w)
        stdscr.addstr(3, 2, f"[{'█' * filled_before}{'░' * (bar_w - filled_before)}]  {pct_before:3d}%")
        stdscr.addstr(4, 2, f"{i - 1} / {total} terminées — floutage en cours...   ")
        stdscr.refresh()

        try:
            _blur_image(src, jobs[src])
        except Exception as e:
            errors.append((src.name, str(e)))

        # Mise à jour après traitement
        pct = int(i / total * 100)
        filled = int(i / total * bar_w)
        stdscr.addstr(3, 2, f"[{'█' * filled}{'░' * (bar_w - filled)}]  {pct:3d}%")
        stdscr.addstr(4, 2, f"{i} / {total} terminées                              ")
        stdscr.refresh()

    stdscr.addstr(6, 2, "─" * (w - 4))
    ok = total - len(errors)
    stdscr.addstr(7, 2, f"{ok} image(s) floutée(s) avec succès.", curses.A_BOLD)

    if errors:
        stdscr.addstr(8, 2, f"{len(errors)} erreur(s) :", curses.A_BOLD)
        for j, (name, err) in enumerate(errors[:h - 12]):
            stdscr.addstr(9 + j, 4, f"{name}: {err}")

    stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()


def _show_message(stdscr, msg):
    stdscr.erase()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(0, 0, " F2 — Flouter des visages ".center(w), curses.A_BOLD | curses.A_REVERSE)
    stdscr.addstr(4, 2, msg, curses.A_BOLD)
    stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
    stdscr.refresh()
    stdscr.getch()
