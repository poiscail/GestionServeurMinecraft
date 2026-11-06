import glob, os, re, shutil, subprocess, threading, time, zipfile

JOIN = re.compile(r"\]: (\w+) joined the game")
LEAVE = re.compile(r"\]: (\w+) left the game")


def java_par_defaut():
    trouves = sorted(glob.glob(os.path.expanduser("~/.jdks/*/bin/java.exe")))
    return trouves[-1] if trouves else "java"


def maj_joueurs(joueurs, ligne):
    """Met à jour l'ensemble des joueurs d'après une ligne de log."""
    if m := JOIN.search(ligne):
        joueurs.add(m[1])
    elif m := LEAVE.search(ligne):
        joueurs.discard(m[1])


def nom_monde(dossier):
    props = os.path.join(dossier, "server.properties")
    if os.path.exists(props):
        for l in open(props, encoding="utf-8"):
            if l.startswith("level-name="):
                return l.split("=", 1)[1].strip()
    return "world"


def port(dossier):
    props = os.path.join(dossier, "server.properties")
    if os.path.exists(props):
        for l in open(props, encoding="utf-8"):
            if l.startswith("server-port=") and l.split("=", 1)[1].strip().isdigit():
                return int(l.split("=", 1)[1])
    return 25565


def sauvegarder(dossier, dest=None, garder=10):
    """Zippe le monde (level-name de server.properties) ; renvoie le chemin du zip."""
    monde = nom_monde(dossier)
    src = os.path.join(dossier, monde)
    if not os.path.isdir(src):
        raise FileNotFoundError(f"Monde introuvable : {src}")
    dest = dest or os.path.join(dossier, "sauvegardes")
    os.makedirs(dest, exist_ok=True)
    chemin = os.path.join(dest, f"{monde}_{time.strftime('%Y%m%d_%H%M%S')}.zip")
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as z:
        for racine, _, fichiers in os.walk(src):
            for f in fichiers:
                p = os.path.join(racine, f)
                try:
                    z.write(p, os.path.relpath(p, dossier))
                except OSError:  # session.lock est verrouillé par le serveur
                    pass
    anciens = sorted(glob.glob(os.path.join(dest, f"{monde}_*.zip")))
    for vieux in anciens[:-garder]:  # ne garde que les `garder` plus récentes
        os.remove(vieux)
    return chemin


def lister_mods(dossier):
    d = os.path.join(dossier, "mods")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def ajouter_mod(dossier, fichier):
    d = os.path.join(dossier, "mods")
    os.makedirs(d, exist_ok=True)
    shutil.copy(fichier, d)


def retirer_mod(dossier, nom):
    os.remove(os.path.join(dossier, "mods", nom))


class Serveur:
    def __init__(self, sur_ligne):
        self.sur_ligne = sur_ligne
        self.proc = None
        self.joueurs = set()
        self.pret = False  # vrai une fois le monde chargé ("Done")

    @property
    def actif(self):
        return self.proc is not None and self.proc.poll() is None

    def demarrer(self, java, jar, ram_mo):
        if self.actif:
            return
        self.joueurs.clear()
        self.pret = False
        self.proc = subprocess.Popen(
            [java, f"-Xmx{ram_mo}M", f"-Xms{ram_mo}M", "-jar", jar, "nogui"],
            cwd=os.path.dirname(jar), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._lire, args=(self.proc,), daemon=True).start()

    def _lire(self, proc):
        for ligne in proc.stdout:
            maj_joueurs(self.joueurs, ligne)
            self.pret = self.pret or "Done (" in ligne
            self.sur_ligne(ligne.rstrip())
        self.joueurs.clear()
        self.sur_ligne("[Serveur arrêté]")

    def commande(self, texte):
        if self.actif:
            self.proc.stdin.write(texte + "\n")
            self.proc.stdin.flush()

    def arreter(self, attendre=60):
        if self.actif:
            self.commande("stop")
            try:
                self.proc.wait(attendre)
            except subprocess.TimeoutExpired:
                self.proc.kill()
