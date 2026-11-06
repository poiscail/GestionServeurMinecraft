import os, tempfile, zipfile
import serveur as sv


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


if __name__ == "__main__":
    test_joueurs()
    test_sauvegarde_et_mods()
    test_rotation()
    print("OK")
