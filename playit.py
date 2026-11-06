"""Agent playit.gg officiel (github.com/playit-cloud/playit-agent) : adresse publique sans ouvrir de port."""
import json, os, re, subprocess, threading, urllib.request, webbrowser

DOSSIER = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GestionServeurMinecraft", "playit")
EXE = os.path.join(DOSSIER, "playit.exe")
API = "https://api.github.com/repos/playit-cloud/playit-agent/releases/latest"
CLAIM = re.compile(r"https://playit\.gg/claim/\S+")
ADRESSE = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:joinmc\.link|playit\.gg|ply\.gg)(?::\d+)?\b")


def telecharger():
    """Télécharge l'agent depuis la release officielle (une seule fois)."""
    if os.path.exists(EXE):
        return
    os.makedirs(DOSSIER, exist_ok=True)
    rel = json.load(urllib.request.urlopen(urllib.request.Request(API, headers={"User-Agent": "GestionServeurMinecraft"}), timeout=30))
    url = next(a["browser_download_url"] for a in rel["assets"] if a["name"] == "playit-windows-x86_64-signed.exe")
    if not url.startswith("https://github.com/playit-cloud/playit-agent/"):
        raise ValueError("URL inattendue")
    with urllib.request.urlopen(url, timeout=120) as r, open(EXE + ".tmp", "wb") as f:
        f.write(r.read())
    os.replace(EXE + ".tmp", EXE)


class Playit:
    def __init__(self, sur_ligne, sur_adresse):
        self.sur_ligne, self.sur_adresse = sur_ligne, sur_adresse
        self.proc = None
        self.claim_ouvert = False

    @property
    def actif(self):
        return self.proc is not None and self.proc.poll() is None

    def demarrer(self):
        if self.actif:
            return
        telecharger()
        self.proc = subprocess.Popen([EXE, "--stdout"], cwd=DOSSIER, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace",
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        threading.Thread(target=self._lire, args=(self.proc,), daemon=True).start()

    def _lire(self, proc):
        for l in proc.stdout:
            l = l.rstrip()
            self.sur_ligne(l)
            if m := CLAIM.search(l):
                if not self.claim_ouvert:
                    self.claim_ouvert = True
                    webbrowser.open(m[0])  # l'utilisateur valide lui-même la liaison du compte
            elif m := ADRESSE.search(l):
                self.sur_adresse(m[0])

    def arreter(self):
        if self.actif:
            # /T : playit.exe lance un processus fils (playitd) qu'un simple terminate() laisserait tourner
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.proc.pid)], capture_output=True)
