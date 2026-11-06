# Gestion Serveur Minecraft

Appli Windows (Python + Tkinter, aucune dépendance) pour piloter un serveur Minecraft : démarrer/arrêter, console en direct avec commandes, joueurs connectés, sauvegardes du monde (manuelles ou automatiques) et gestion du dossier `mods`.

## Utilisation
1. Télécharge `GestionServeurMinecraft.exe` dans les Releases GitHub et double-clique (ou `lancer.bat` avec Python 3.10+).
2. Indique Java (détecté dans `~/.jdks`, sinon `java`), choisis le `.jar` du serveur et la RAM.
3. Onglet Mods > « Importer un modpack… » : `.mrpack` (Modrinth), `.zip` CurseForge ou `.zip` de mods. Les mods serveur sont téléchargés, les mods client-only ignorés, les configs copiées sans rien écraser (monde protégé), l'ancien dossier mods est sauvegardé. Pour Fabric, le serveur correspondant peut être téléchargé ; pour Forge/NeoForge/Quilt, la version requise est indiquée.
4. Les sauvegardes sont des zip dans `sauvegardes/` à côté du `.jar`.

## Test
```
python test_serveur.py
```
