# Gestion Serveur Minecraft

Appli Windows (Python + Tkinter, aucune dépendance) pour piloter un serveur Minecraft : démarrer/arrêter, console en direct avec commandes, joueurs connectés, sauvegardes du monde (manuelles ou automatiques) et gestion du dossier `mods`.

## Utilisation
1. Télécharge `GestionServeurMinecraft.exe` dans les Releases GitHub et double-clique (ou `lancer.bat` avec Python 3.10+).
2. Indique Java (détecté dans `~/.jdks`, sinon `java`), choisis le `.jar` du serveur et la RAM.
3. Onglet Mods > « Importer un modpack… » : `.mrpack` (Modrinth), `.zip` CurseForge ou `.zip` de mods. Les mods serveur sont téléchargés, les mods client-only ignorés, les configs copiées sans rien écraser (monde protégé), l'ancien dossier mods est sauvegardé. Pour Fabric, le serveur correspondant peut être téléchargé ; pour Forge/NeoForge/Quilt, la version requise est indiquée.
4. Les sauvegardes sont des zip dans `sauvegardes/` à côté du `.jar`.

## En ligne avec des amis
Onglet **En ligne** :
- **Mettre en ligne** : télécharge l'agent officiel [playit.gg](https://playit.gg), ouvre la page de liaison de ton compte (à valider toi-même) ; l'adresse publique s'affiche, bouton **Copier**.
- **Mode veille** : serveur éteint, l'appli écoute le port ; un ping affiche un message, une connexion démarre le serveur. **Arrêt auto** après X minutes sans joueur.
- **Partager le modpack** : génère un pack [packwiz](https://packwiz.infra.link) d'après les mods (retrouvés sur Modrinth) et le publie dans un dépôt GitHub public `ModpackServeur` (nécessite `gh` connecté). Les mods introuvables sur Modrinth sont ignorés.
- **Générer le kit amis** : `KitServeur.zip` avec Prism Launcher portable (officiel, inchangé, licence GPL incluse), une instance réglée sur la bonne version/loader qui synchronise les mods au lancement, le serveur dans la liste, et une fiche d'aide `LISEZ-MOI.txt`.

Onglet **État** : en ligne/hors ligne, joueurs, CPU/RAM du serveur.

## Test
```
python test_serveur.py
```
