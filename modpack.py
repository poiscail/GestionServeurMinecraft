"""Import d'un modpack (.mrpack Modrinth, .zip CurseForge ou simple .zip de mods) côté serveur."""
import hashlib, json, os, shutil, time, urllib.parse, urllib.request, zipfile
from concurrent.futures import ThreadPoolExecutor

import serveur as sv

HOTES = ("cdn.modrinth.com", "github.com", "raw.githubusercontent.com", "gitlab.com")  # hôtes autorisés par la spec .mrpack
UA = {"User-Agent": "GestionServeurMinecraft/1.2"}
LOADERS = {"fabric-loader": "fabric", "quilt-loader": "quilt", "forge": "forge", "neoforge": "neoforge"}


def _sur(dossier, rel):
    """Chemin sous `dossier`, ou None s'il en sort (zip-slip)."""
    base = os.path.realpath(dossier)
    p = os.path.realpath(os.path.join(base, rel))
    return p if p.startswith(base + os.sep) else None


def _lire(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read(), r.url


def _ecrire(dest, data):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)


def _verifier(data, hashes):
    for algo in ("sha512", "sha1"):
        if algo in hashes and hashlib.new(algo, data).hexdigest() != hashes[algo]:
            raise ValueError("empreinte incorrecte")


def sauvegarder_mods(dossier):
    """Zippe l'ancien dossier mods (s'il n'est pas vide) avant toute modification."""
    d = os.path.join(dossier, "mods")
    if not sv.lister_mods(dossier):
        return None
    os.makedirs(os.path.join(dossier, "sauvegardes"), exist_ok=True)
    base = os.path.join(dossier, "sauvegardes", f"mods_{time.strftime('%Y%m%d_%H%M%S')}")
    return shutil.make_archive(base, "zip", d)


def _overrides(z, dossier, prefixes, monde):
    """Copie les overrides sans jamais écraser un fichier existant ni toucher au monde."""
    n = 0
    for pre in prefixes:  # server-overrides d'abord : le premier fichier posé gagne
        for info in z.infolist():
            if not info.filename.startswith(pre) or info.is_dir():
                continue
            rel = info.filename[len(pre):]
            dest = _sur(dossier, rel)
            if not dest or rel.split("/")[0] == monde or os.path.exists(dest):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with z.open(info) as s, open(dest, "wb") as d:
                shutil.copyfileobj(s, d)
            n += 1
    return n


def _telecharger_tout(taches, dossier, log):
    """taches : (url, chemin relatif ou None, empreintes). Renvoie (ok, echecs)."""
    ok, echecs = 0, []

    def un(t):
        url, rel, hashes = t
        data, finale = _lire(url)
        _verifier(data, hashes)
        rel = rel or "mods/" + os.path.basename(urllib.parse.unquote(urllib.parse.urlparse(finale).path))
        dest = _sur(dossier, rel)
        if not dest:
            raise ValueError("chemin refusé")
        _ecrire(dest, data)
        return rel

    with ThreadPoolExecutor(8) as ex:
        for t, f in [(t, ex.submit(un, t)) for t in taches]:
            try:
                log(f"[Modpack] {ok + len(echecs) + 1}/{len(taches)} {f.result()}")
                ok += 1
            except Exception as e:
                echecs.append(f"{t[1] or t[0]} ({e})")
    return ok, echecs


def installer(chemin, dossier, log=print):
    """Installe le modpack dans `dossier` ; renvoie un dict de résumé."""
    monde = sv.nom_monde(dossier)
    info = {"mc": None, "loader": None, "loader_version": None, "installes": 0, "ignores": 0, "echecs": [], "overrides": 0}
    with zipfile.ZipFile(chemin) as z:
        noms = z.namelist()
        info["sauvegarde_mods"] = sauvegarder_mods(dossier)
        if "modrinth.index.json" in noms:
            idx = json.loads(z.read("modrinth.index.json"))
            dep = idx.get("dependencies", {})
            info["mc"] = dep.get("minecraft")
            for k, v in dep.items():
                if k in LOADERS:
                    info["loader"], info["loader_version"] = LOADERS[k], v
            taches = []
            for f in idx.get("files", []):
                if f.get("env", {}).get("server") == "unsupported":
                    info["ignores"] += 1
                    continue
                urls = [u for u in f.get("downloads", []) if urllib.parse.urlparse(u).scheme == "https"
                        and urllib.parse.urlparse(u).hostname in HOTES]
                if urls:
                    taches.append((urls[0], f["path"], f.get("hashes", {})))
                else:
                    info["echecs"].append(f"{f.get('path')} (aucune URL autorisée)")
            info["installes"], ech = _telecharger_tout(taches, dossier, log)
            info["echecs"] += ech
            info["overrides"] = _overrides(z, dossier, ("server-overrides/", "overrides/"), monde)
        elif "manifest.json" in noms:
            man = json.loads(z.read("manifest.json"))
            info["mc"] = man.get("minecraft", {}).get("version")
            ml = man.get("minecraft", {}).get("modLoaders") or [{}]
            lid = next((m["id"] for m in ml if m.get("primary")), ml[0].get("id", ""))
            if "-" in lid:
                info["loader"], info["loader_version"] = lid.split("-", 1)
            taches = [(f"https://www.curseforge.com/api/v1/mods/{f['projectID']}/files/{f['fileID']}/download", None, {})
                      for f in man.get("files", []) if f.get("required", True)]
            info["installes"], info["echecs"] = _telecharger_tout(taches, dossier, log)
            info["overrides"] = _overrides(z, dossier, (man.get("overrides", "overrides") + "/",), monde)
        else:  # simple zip de mods
            for n in noms:
                if n.lower().endswith(".jar"):
                    dest = _sur(dossier, "mods/" + os.path.basename(n))
                    if dest and not os.path.exists(dest):
                        _ecrire(dest, z.read(n))
                        info["installes"] += 1
    return info


def installer_fabric(dossier, mc, loader_version):
    """Télécharge fabric-server-launch.jar (serveur Fabric prêt à lancer) ; renvoie son chemin."""
    versions = json.loads(_lire("https://meta.fabricmc.net/v2/versions/installer")[0])
    inst = next(v["version"] for v in versions if v.get("stable"))
    url = f"https://meta.fabricmc.net/v2/versions/loader/{mc}/{loader_version}/{inst}/server/jar"
    dest = os.path.join(dossier, "fabric-server-launch.jar")
    _ecrire(dest, _lire(url)[0])
    return dest
