"""Partage du modpack (packwiz) et kit pour les amis (Prism Launcher portable + instance préréglée)."""
import hashlib, json, os, shutil, struct, subprocess, urllib.parse, urllib.request, zipfile

import modpack as mp
import serveur as sv

CACHE = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GestionServeurMinecraft", "cache")
UA = {"User-Agent": "GestionServeurMinecraft"}
COMPOSANTS = {"fabric": "net.fabricmc.fabric-loader", "quilt": "org.quiltmc.quilt-loader",
              "forge": "net.minecraftforge", "neoforge": "net.neoforged"}


def _toml(s):
    return json.dumps(s, ensure_ascii=False)  # une chaîne JSON est une chaîne TOML valide


def _api(url, donnees=None):
    req = urllib.request.Request(url, data=json.dumps(donnees).encode() if donnees else None,
                                 headers={**UA, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def generer_pack(dossier, sortie, nom, mc, loader, loader_version):
    """Écrit un pack packwiz dans `sortie` d'après les mods du serveur. Renvoie (nb ajoutés, mods introuvables)."""
    jars = [j for j in sv.lister_mods(dossier) if j.endswith(".jar")]
    sha1 = {j: hashlib.sha1(open(os.path.join(dossier, "mods", j), "rb").read()).hexdigest() for j in jars}
    versions = _api("https://api.modrinth.com/v2/version_files", {"hashes": list(sha1.values()), "algorithm": "sha1"}) if jars else {}
    ids = sorted({v["project_id"] for v in versions.values()})
    projets = {p["id"]: p for p in _api("https://api.modrinth.com/v2/projects?ids=" + urllib.parse.quote(json.dumps(ids)))} if ids else {}
    shutil.rmtree(os.path.join(sortie, "mods"), ignore_errors=True)
    os.makedirs(os.path.join(sortie, "mods"))
    index, manquants = [], []
    for j in jars:
        v = versions.get(sha1[j])
        if not v:
            manquants.append(j)
            continue
        f = next(f for f in v["files"] if f["hashes"]["sha1"] == sha1[j])
        p = projets.get(v["project_id"], {})
        cote = "server" if p.get("client_side") == "unsupported" else "client" if p.get("server_side") == "unsupported" else "both"
        meta = (f'name = {_toml(p.get("title", j))}\nfilename = {_toml(j)}\nside = "{cote}"\n\n[download]\n'
                f'url = {_toml(f["url"])}\nhash-format = "sha512"\nhash = "{f["hashes"]["sha512"]}"\n')
        chemin = f"mods/{os.path.splitext(j)[0]}.pw.toml"
        open(os.path.join(sortie, chemin), "w", encoding="utf-8", newline="\n").write(meta)
        index.append(f'[[files]]\nfile = {_toml(chemin)}\nhash = "{hashlib.sha256(meta.encode()).hexdigest()}"\nmetafile = true\n')
    idx = 'hash-format = "sha256"\n\n' + "\n".join(index)
    open(os.path.join(sortie, "index.toml"), "w", encoding="utf-8", newline="\n").write(idx)
    pack = (f'name = {_toml(nom)}\npack-format = "packwiz:1.1.0"\n\n[index]\nfile = "index.toml"\nhash-format = "sha256"\n'
            f'hash = "{hashlib.sha256(idx.encode()).hexdigest()}"\n\n[versions]\nminecraft = {_toml(mc)}\n{loader} = {_toml(loader_version)}\n')
    open(os.path.join(sortie, "pack.toml"), "w", encoding="utf-8", newline="\n").write(pack)
    return len(index), manquants


def publier(sortie, repo="ModpackServeur"):
    """Pousse le pack dans un dépôt GitHub public (le crée s'il n'existe pas). Renvoie l'URL raw de pack.toml."""
    def run(*a):
        return subprocess.run(a, cwd=sortie, capture_output=True, text=True, check=True).stdout.strip()
    owner = run("gh", "api", "user", "-q", ".login")
    if not os.path.isdir(os.path.join(sortie, ".git")):
        run("git", "init", "-q", "-b", "main")
    run("git", "add", "-A")
    if run("git", "status", "--porcelain"):
        run("git", "-c", f"user.name={owner}", "-c", f"user.email={owner}@users.noreply.github.com", "commit", "-qm", "Mise à jour du modpack")
    if "origin" not in run("git", "remote"):
        run("gh", "repo", "create", f"{owner}/{repo}", "--public", "--source", ".", "--remote", "origin")
    run("git", "push", "-q", "-u", "origin", "main")
    return f"https://raw.githubusercontent.com/{owner}/{repo}/main/pack.toml"


def servers_dat(nom, adresse):
    """NBT non compressé minimal : une seule entrée de serveur."""
    def s(cle, val):
        k, v = cle.encode(), val.encode("utf-8")
        return b"\x08" + struct.pack(">H", len(k)) + k + struct.pack(">H", len(v)) + v
    return (b"\x0a\x00\x00" + b"\x09" + struct.pack(">H", 7) + b"servers" + b"\x0a" + struct.pack(">i", 1)
            + s("name", nom) + s("ip", adresse) + b"\x00" + b"\x00")


def _telecharger(url, nom):
    os.makedirs(CACHE, exist_ok=True)
    dest = os.path.join(CACHE, nom)
    if not os.path.exists(dest):
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r, open(dest + ".tmp", "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(dest + ".tmp", dest)
    return dest


def _asset(repo, motif):
    rel = _api(f"https://api.github.com/repos/{repo}/releases/latest")
    a = next(a for a in rel["assets"] if motif in a["name"] and a["name"].endswith(".zip"))
    return a["browser_download_url"], a["name"]


AIDE = """KIT POUR REJOINDRE LE SERVEUR « {nom} »

1. Dézippe ce dossier où tu veux (Bureau, Documents…). Ne le lance pas depuis le zip.
2. Ouvre « prismlauncher.exe ».
3. Au premier lancement, choisis ta langue puis connecte-toi avec le compte Microsoft
   qui possède Minecraft Java (bouton « Comptes » → « Ajouter un compte Microsoft »).
   Si Prism propose d'installer Java, accepte.
4. Double-clique sur l'instance « {nom} » puis « Jouer ». Au démarrage, les mods du
   serveur se téléchargent tout seuls (une petite fenêtre s'ouvre, c'est normal).
5. Dans Minecraft : Multijoueur → « {nom} » → Rejoindre.
   Si le serveur dormait, il démarre : attends une minute puis réessaie.

Adresse du serveur : {adresse}
Version : Minecraft {mc} ({loader} {lv}) — ne la change pas.

Prism Launcher est un logiciel libre (licence GPL-3.0, voir LICENSE-PrismLauncher.txt),
fourni sans modification : https://prismlauncher.org
Si un mod manque ou plante, ferme le jeu et relance « Jouer » : la synchro se refait.
"""


def generer_kit(sortie, nom, mc, loader, loader_version, pack_url, adresse, log=print):
    """Crée KitServeur.zip : Prism portable + instance préréglée + synchro packwiz + aide. Renvoie le chemin du zip."""
    prism_url, prism_nom = _asset("PrismLauncher/PrismLauncher", "Windows-MinGW-w64-Portable")
    log("[Kit] Téléchargement de Prism Launcher (si besoin)…")
    prism = _telecharger(prism_url, prism_nom)
    boot = _telecharger("https://github.com/packwiz/packwiz-installer-bootstrap/releases/latest/download/packwiz-installer-bootstrap.jar",
                        "packwiz-installer-bootstrap.jar")
    licence = _telecharger("https://raw.githubusercontent.com/PrismLauncher/PrismLauncher/develop/LICENSE", "LICENSE-PrismLauncher.txt")
    kit = os.path.join(sortie, "KitServeur")
    shutil.rmtree(kit, ignore_errors=True)
    with zipfile.ZipFile(prism) as z:
        z.extractall(kit)
    inst = os.path.join(kit, "instances", nom)
    mcdir = os.path.join(inst, ".minecraft")
    os.makedirs(mcdir)
    shutil.copy(boot, mcdir)
    open(os.path.join(inst, "mmc-pack.json"), "w").write(json.dumps({"formatVersion": 1, "components": [
        {"uid": "net.minecraft", "version": mc, "important": True},
        {"uid": COMPOSANTS[loader], "version": loader_version}]}))
    open(os.path.join(inst, "instance.cfg"), "w", encoding="utf-8").write(
        f'[General]\nConfigVersion=1.2\nInstanceType=OneSix\nname={nom}\nOverrideCommands=true\n'
        f'PreLaunchCommand="$INST_JAVA" -jar packwiz-installer-bootstrap.jar {pack_url}\n')
    open(os.path.join(mcdir, "servers.dat"), "wb").write(servers_dat(nom, adresse))
    shutil.copy(licence, os.path.join(kit, "LICENSE-PrismLauncher.txt"))
    open(os.path.join(kit, "LISEZ-MOI.txt"), "w", encoding="utf-8").write(
        AIDE.format(nom=nom, adresse=adresse, mc=mc, loader=loader, lv=loader_version))
    zip_ = shutil.make_archive(os.path.join(sortie, "KitServeur"), "zip", sortie, "KitServeur")
    shutil.rmtree(kit)
    return zip_
