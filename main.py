import curses

import f1_supprimer_originaux
import f2_flouter_visages
import f3_supprimer_originaux_floutes


MENU_ITEMS = [
    ("F1", "Supprimer les originaux retouchés"),
    ("F2", "Flouter des images"),
    ("F3", "Supprimer les originaux qui ont été floutés"),
    ("F4", "Quitter"),
]

KEY_MAP = {
    curses.KEY_F1: 0,
    curses.KEY_F2: 1,
    curses.KEY_F3: 2,
    curses.KEY_F4: 3,
}

ASCII_ART = [
r" _____/\\\\\\\\\_____/\\\\\\\\\\\\\____/\\\\____________/\\\\_",        
r"  ___/\\\\\\\\\\\\\__\/\\\/////////\\\_\/\\\\\\________/\\\\\\_",       
r"   __/\\\/////////\\\_\/\\\_______\/\\\_\/\\\//\\\____/\\\//\\\_",      
r"    _\/\\\_______\/\\\_\/\\\\\\\\\\\\\/__\/\\\\///\\\/\\\/_\/\\\_",     
r"     _\/\\\\\\\\\\\\\\\_\/\\\/////////____\/\\\__\///\\\/___\/\\\_",    
r"      _\/\\\/////////\\\_\/\\\_____________\/\\\____\///_____\/\\\_",   
r"       _\/\\\_______\/\\\_\/\\\_____________\/\\\_____________\/\\\_",  
r"        _\/\\\_______\/\\\_\/\\\_____________\/\\\_____________\/\\\_", 
r"         _\///________\///__\///______________\///______________\///__",
]
SUBTITLE = "Anatoly's Photo Manager"


def draw_menu(stdscr, selected):
    stdscr.erase()
    h, w = stdscr.getmaxyx()

    # ASCII art centré
    art_w = max(len(line) for line in ASCII_ART)
    art_x = max(0, (w - art_w) // 2)
    for i, line in enumerate(ASCII_ART):
        try:
            stdscr.addstr(1 + i, art_x, line, curses.A_BOLD)
        except curses.error:
            pass

    # Sous-titre
    sub_x = max(0, (w - len(SUBTITLE)) // 2)
    stdscr.addstr(11, sub_x, SUBTITLE, curses.A_DIM)

    # Séparateur
    stdscr.addstr(12, 2, "─" * (w - 4))

    # Options du menu
    for i, (key, label) in enumerate(MENU_ITEMS):
        y = 14 + i * 2
        x = max(0, (w - 44) // 2)
        attr = curses.A_REVERSE if i == selected else curses.A_NORMAL
        stdscr.addstr(y, x, f"  [{key}]  {label:<37}", attr)

    hint = "Naviguez avec ↑↓ ou appuyez sur Fn | Entrée pour valider"
    stdscr.addstr(h - 2, max(0, (w - len(hint)) // 2), hint, curses.A_DIM)
    stdscr.refresh()


def run_option(stdscr, index):
    if index == 3:
        return False  # Quitter

    if index == 0:
        f1_supprimer_originaux.run(stdscr)
    elif index == 1:
        f2_flouter_visages.run(stdscr)
    elif index == 2:
        f3_supprimer_originaux_floutes.run(stdscr)
    else:
        # Placeholder (ne devrait pas arriver)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        label = MENU_ITEMS[index][1]
        stdscr.addstr(2, 2, f">>> {label}", curses.A_BOLD)
        stdscr.addstr(4, 2, "[Fonction à implémenter]")
        stdscr.addstr(h - 2, 2, "Appuyez sur une touche pour revenir au menu...", curses.A_DIM)
        stdscr.refresh()
        stdscr.getch()

    return True


def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)

    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)

    selected = 0

    while True:
        draw_menu(stdscr, selected)
        key = stdscr.getch()

        if key in KEY_MAP:
            selected = KEY_MAP[key]
            if not run_option(stdscr, selected):
                break

        elif key == curses.KEY_UP:
            selected = (selected - 1) % len(MENU_ITEMS)

        elif key == curses.KEY_DOWN:
            selected = (selected + 1) % len(MENU_ITEMS)

        elif key in (curses.KEY_ENTER, ord("\n"), ord("\r")):
            if not run_option(stdscr, selected):
                break


if __name__ == "__main__":
    import sys, os, shutil, subprocess

    if not sys.stdin.isatty():
        # Pas dans un terminal : se relancer dans le premier émulateur disponible
        binary = os.path.abspath(sys.argv[0])
        for term, args in [
            ("konsole", ["konsole", "--hold", "-e", binary]),
            ("xterm",   ["xterm", "-hold", "-e", binary]),
            ("xfce4-terminal", ["xfce4-terminal", "--hold", "-x", binary]),
            ("gnome-terminal", ["gnome-terminal", "--", binary]),
        ]:
            if shutil.which(term):
                subprocess.Popen(args)
                sys.exit(0)
        # Aucun terminal trouvé : message d'erreur via zenity ou stderr
        if shutil.which("zenity"):
            subprocess.run(["zenity", "--error", "--text",
                            "APM nécessite un terminal.\nInstallez konsole ou xterm."])
        else:
            sys.stderr.write("APM doit être lancé dans un terminal interactif.\n")
        sys.exit(1)

    curses.wrapper(main)
