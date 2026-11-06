# Gestion Serveur Minecraft

Appli Windows (Python + Tkinter, aucune dépendance) pour piloter un serveur Minecraft : démarrer/arrêter, console en direct avec commandes, joueurs connectés, sauvegardes du monde (manuelles ou automatiques) et gestion du dossier `mods`.

## Utilisation
1. Double-clic sur `lancer.bat` (Python 3.10+ requis).
2. Indique Java (détecté dans `~/.jdks`, sinon `java`), choisis le `.jar` du serveur et la RAM.
3. Les sauvegardes sont des zip dans `sauvegardes/` à côté du `.jar`.

## Test
```
python test_serveur.py
```
