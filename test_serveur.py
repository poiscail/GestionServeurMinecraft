import os, tempfile, zipfile
import json
import modpack as mp
import partage
import serveur as sv
import socket
import veille


def test_joueurs():
    j = set()
    sv.maj_joueurs(j, "[10:00:00] [Server thread/INFO]: Bob joined the game")
    assert j == {"Bob"}
    sv.maj_joueurs(j, "[10:01:00] [Server thread/INFO]: Bob left the game")
    assert j == set()


def test_sauvegarde_et_mods():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "world"))
    open(os.path.join(d, "world", "level.dat"), "w").write("x")
    with zipfile.ZipFile(sv.sauvegarder(d)) as z:
        assert "world/level.dat" in z.namelist()
    f = os.path.join(d, "a.jar")
    open(f, "w").write("m")
    sv.ajouter_mod(d, f)
    assert sv.lister_mods(d) == ["a.jar"]
    sv.retirer_mod(d, "a.jar")
    assert sv.lister_mods(d) == []


def test_rotation():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "world"))
    dest = os.path.join(d, "sauvegardes")
    os.makedirs(dest)
    for n in ("20000101_000000", "20000102_000000"):
        open(os.path.join(dest, f"world_{n}.zip"), "w").close()
    sv.sauvegarder(d, garder=2)
    assert len(os.listdir(dest)) == 2 and "world_20000101_000000.zip" not in os.listdir(dest)


def test_modpack_hors_ligne():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "mods"))
    open(os.path.join(d, "mods", "vieux.jar"), "w").write("v")
    os.makedirs(os.path.join(d, "world"))
    open(os.path.join(d, "world", "level.dat"), "w").write("garde")
    open(os.path.join(d, "config.txt"), "w").write("garde")
    idx = {"dependencies": {"minecraft": "1.21.1", "fabric-loader": "0.16.0"},
           "files": [{"path": "mods/client.jar", "env": {"server": "unsupported"}, "downloads": []},
                     {"path": "mods/mauvais.jar", "downloads": ["https://evil.example/x.jar"]}]}
    pack = os.path.join(d, "p.mrpack")
    with zipfile.ZipFile(pack, "w") as z:
        z.writestr("modrinth.index.json", json.dumps(idx))
        z.writestr("overrides/config.txt", "ecrase")
        z.writestr("overrides/nouveau.txt", "ok")
        z.writestr("overrides/world/level.dat", "ecrase")
        z.writestr("overrides/../../evasion.txt", "x")
    info = mp.installer(pack, d)
    assert (info["mc"], info["loader"], info["ignores"], info["overrides"]) == ("1.21.1", "fabric", 1, 1)
    assert len(info["echecs"]) == 1  # hôte non autorisé
    assert open(os.path.join(d, "config.txt")).read() == "garde"
    assert open(os.path.join(d, "world", "level.dat")).read() == "garde"
    assert not os.path.exists(os.path.join(os.path.dirname(d), "evasion.txt"))
    assert zipfile.ZipFile(info["sauvegarde_mods"]).namelist() == ["vieux.jar"]


def test_zip_de_mods():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "m.zip")
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("dossier/a.jar", "x")
        z.writestr("lisez.txt", "x")
    assert mp.installer(p, d)["installes"] == 1 and sv.lister_mods(d) == ["a.jar"]


def _poignee(etat, port):
    corps = b"\x00" + veille._encode(767) + veille._chaine("localhost") + port.to_bytes(2, "big") + bytes([etat])
    return veille._encode(len(corps)) + corps


def test_veille_ping_et_reveil():
    reveils = []
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    v = veille.Veille(port, lambda: reveils.append(1))
    v.ouvrir()
    try:
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(_poignee(1, port) + b"\x01\x00")
        rep = veille._lire_paquet(c)
        assert b"veille" in rep and not reveils
        c.close()
        c = socket.create_connection(("127.0.0.1", port), timeout=5)
        c.sendall(_poignee(2, port) + veille._paquet(0, veille._chaine("Bob")))
        assert b"marre" in veille._lire_paquet(c)
        c.close()
        for _ in range(50):
            if reveils:
                break
            import time; time.sleep(0.1)
        assert reveils and v.demarrage
    finally:
        v.fermer()


def test_pack_vide_et_servers_dat():
    d = tempfile.mkdtemp()
    n, manquants = partage.generer_pack(d, d, "T", "1.21.1", "fabric", "0.16.14")
    pack = open(os.path.join(d, "pack.toml"), encoding="utf-8").read()
    assert n == 0 and 'fabric = "0.16.14"' in pack and 'minecraft = "1.21.1"' in pack
    dat = partage.servers_dat("Nom", "a.joinmc.link")
    assert b"servers" in dat and b"a.joinmc.link" in dat and dat[-2:] == b"\x00\x00"


if __name__ == "__main__":
    test_joueurs()
    test_sauvegarde_et_mods()
    test_rotation()
    test_modpack_hors_ligne()
    test_zip_de_mods()
    test_veille_ping_et_reveil()
    test_pack_vide_et_servers_dat()
    print("OK")
