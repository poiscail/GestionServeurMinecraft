import json, os, queue, threading, time, tkinter as tk
from tkinter import filedialog, messagebox, ttk
import modpack as mp
import serveur as sv

BG, PANEL, CHAMP, FG, DIM, ACCENT = "#16181d", "#1f2229", "#292d36", "#e8eaed", "#8b909a", "#5b8def"
VERT, ROUGE, ORANGE = "#3ddc84", "#ef5350", "#f5a623"
POLICE = ("Segoe UI", 10)
CONFIG = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "GestionServeurMinecraft.json")
MAX_LIGNES = 2000


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion serveur Minecraft")
        self.geometry("1000x660")
        self.minsize(760, 480)
        self.configure(bg=BG)
        self._style()
        self.file = queue.Queue()  # lignes de log et messages venant d'autres threads
        self.srv = sv.Serveur(self.file.put)
        cfg = self._charger()
        self.java = tk.StringVar(value=cfg.get("java") or sv.java_par_defaut())
        self.jar = tk.StringVar(value=cfg.get("jar", ""))
        self.ram = tk.StringVar(value=cfg.get("ram", "2048"))
        self.auto = tk.StringVar(value=cfg.get("auto", "0"))
        self.cmd = tk.StringVar()
        self.historique, self.pos_h = [], 0
        self.arret_en_cours = False
        self.sauvegarde_en_cours = False
        self.prochaine_auto = None
        self._construire()
        self.jar.trace_add("write", lambda *_: self.maj_mods())
        self.maj_mods()
        self.protocol("WM_DELETE_WINDOW", self.fermer)
        self.after(100, self.boucle)

    # ---------- style ----------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=CHAMP, font=POLICE,
                    bordercolor=BG, lightcolor=BG, darkcolor=BG, troughcolor=BG, focuscolor=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG)
        s.configure("Dim.TLabel", foreground=DIM)
        s.configure("Panel.TLabel", background=PANEL)
        s.configure("TEntry", fieldbackground=CHAMP, insertcolor=FG, padding=6, bordercolor=CHAMP)
        s.configure("TButton", background=CHAMP, padding=(12, 6), borderwidth=0)
        s.map("TButton", background=[("active", "#353a46"), ("disabled", PANEL)], foreground=[("disabled", DIM)])
        s.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI Semibold", 10), padding=(18, 7))
        s.map("Accent.TButton", background=[("active", "#4a7ae0"), ("disabled", PANEL)])
        s.configure("Stop.TButton", background=ROUGE, foreground="white", font=("Segoe UI Semibold", 10), padding=(18, 7))
        s.map("Stop.TButton", background=[("active", "#d94441"), ("disabled", PANEL)])
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", background=BG, foreground=DIM, padding=(16, 8), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", FG)])

    def _liste(self, parent, **kw):
        return tk.Listbox(parent, bg=PANEL, fg=FG, selectbackground=ACCENT, relief="flat", borderwidth=0,
                          highlightthickness=0, font=POLICE, activestyle="none", **kw)

    # ---------- interface ----------
    def _construire(self):
        haut = ttk.Frame(self, style="Panel.TFrame", padding=12)
        haut.pack(fill="x")
        haut.columnconfigure(1, weight=1)
        ttk.Label(haut, text="Serveur (.jar)", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(haut, textvariable=self.jar).grid(row=0, column=1, sticky="ew")
        ttk.Button(haut, text="Parcourir…", command=self.choisir_jar).grid(row=0, column=2, padx=(8, 0))
        ttk.Label(haut, text="Java", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(haut, textvariable=self.java).grid(row=1, column=1, sticky="ew", pady=(8, 0))
        ligne = ttk.Frame(haut, style="Panel.TFrame")
        ligne.grid(row=1, column=2, pady=(8, 0), padx=(8, 0))
        ttk.Label(ligne, text="RAM (Mo)", style="Panel.TLabel").pack(side="left", padx=(0, 6))
        ttk.Entry(ligne, textvariable=self.ram, width=7).pack(side="left")

        barre = ttk.Frame(self, padding=(12, 10))
        barre.pack(fill="x")
        self.bt = ttk.Button(barre, text="Démarrer", style="Accent.TButton", command=self.basculer)
        self.bt.pack(side="left")
        self.point = tk.Label(barre, text="●", fg=ROUGE, bg=BG, font=("Segoe UI", 14))
        self.point.pack(side="left", padx=(14, 4))
        self.etat = ttk.Label(barre, text="Arrêté")
        self.etat.pack(side="left")
        self.nb_joueurs = ttk.Label(barre, text="", style="Dim.TLabel")
        self.nb_joueurs.pack(side="right")

        self.onglets = ttk.Notebook(self)
        self.onglets.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        c = ttk.Frame(self.onglets, style="Panel.TFrame", padding=8)
        self.onglets.add(c, text="Console")
        self.console = tk.Text(c, bg=PANEL, fg=FG, state="disabled", wrap="word", relief="flat", borderwidth=0,
                               highlightthickness=0, font=("Consolas", 10), padx=6, pady=4)
        sb = ttk.Scrollbar(c, command=self.console.yview)
        self.console.config(yscrollcommand=sb.set)
        saisie = ttk.Frame(c, style="Panel.TFrame")
        saisie.pack(side="bottom", fill="x", pady=(8, 0))
        sb.pack(side="right", fill="y")
        self.console.pack(fill="both", expand=True)
        self.console.tag_config("warn", foreground=ORANGE)
        self.console.tag_config("err", foreground=ROUGE)
        self.console.tag_config("sys", foreground=DIM)
        ttk.Label(saisie, text="›", style="Panel.TLabel", font=("Consolas", 12)).pack(side="left", padx=(0, 6))
        e = ttk.Entry(saisie, textvariable=self.cmd)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", self.envoyer)
        e.bind("<Up>", lambda _: self.naviguer(-1))
        e.bind("<Down>", lambda _: self.naviguer(1))

        j = ttk.Frame(self.onglets, style="Panel.TFrame", padding=12)
        self.onglets.add(j, text="Joueurs")
        self.liste_j = self._liste(j)
        self.liste_j.pack(fill="both", expand=True)

        b = ttk.Frame(self.onglets, style="Panel.TFrame", padding=16)
        self.onglets.add(b, text="Sauvegardes")
        self.bt_sauv = ttk.Button(b, text="Sauvegarder maintenant", command=self.sauvegarde)
        self.bt_sauv.pack(anchor="w")
        f = ttk.Frame(b, style="Panel.TFrame")
        f.pack(anchor="w", pady=14)
        ttk.Label(f, text="Sauvegarde auto toutes les", style="Panel.TLabel").pack(side="left")
        ttk.Entry(f, textvariable=self.auto, width=5).pack(side="left", padx=6)
        ttk.Label(f, text="minutes (0 = désactivée) · les 10 dernières sont gardées", style="Panel.TLabel").pack(side="left")
        self.auto.trace_add("write", lambda *_: self.reset_auto())
        self.etat_b = ttk.Label(b, text="", style="Panel.TLabel", foreground=DIM)
        self.etat_b.pack(anchor="w")

        m = ttk.Frame(self.onglets, style="Panel.TFrame", padding=12)
        self.onglets.add(m, text="Mods")
        bm = ttk.Frame(m, style="Panel.TFrame")
        bm.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(bm, text="Ajouter…", command=self.ajouter_mod).pack(side="left")
        ttk.Button(bm, text="Retirer", command=self.retirer_mod).pack(side="left", padx=8)
        self.bt_pack = ttk.Button(bm, text="Importer un modpack…", command=self.importer_modpack)
        self.bt_pack.pack(side="right")
        self.liste_m = self._liste(m, selectmode="extended")
        self.liste_m.pack(fill="both", expand=True)

    # ---------- utilitaires ----------
    def _charger(self):
        try:
            return json.load(open(CONFIG, encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _enregistrer(self):
        try:
            json.dump({"java": self.java.get(), "jar": self.jar.get(), "ram": self.ram.get(), "auto": self.auto.get()},
                      open(CONFIG, "w", encoding="utf-8"))
        except OSError:
            pass

    def dossier(self):
        return os.path.dirname(self.jar.get()) if self.jar.get() else None

    def log(self, l):
        tag = "err" if ("ERROR" in l or "Exception" in l) else "warn" if "WARN" in l else "sys" if l.startswith("[") and "INFO" not in l and "]:" not in l else ""
        self.console.config(state="normal")
        self.console.insert("end", l + "\n", tag)
        n = int(self.console.index("end-1c").split(".")[0])
        if n > MAX_LIGNES:
            self.console.delete("1.0", f"{n - MAX_LIGNES}.0")
        self.console.see("end")
        self.console.config(state="disabled")

    # ---------- actions ----------
    def choisir_jar(self):
        p = filedialog.askopenfilename(filetypes=[("Jar", "*.jar")])
        if p:
            self.jar.set(os.path.normpath(p))

    def basculer(self):
        if self.srv.actif:
            self.arret_en_cours = True
            self.log("[Arrêt en cours…]")
            threading.Thread(target=self.srv.arreter, daemon=True).start()
        elif os.path.isfile(self.jar.get()) and self.ram.get().isdigit() and int(self.ram.get()) >= 512:
            self._enregistrer()
            try:
                self.srv.demarrer(self.java.get(), self.jar.get(), int(self.ram.get()))
                self.reset_auto()
            except OSError as ex:
                messagebox.showerror("Erreur", f"Impossible de lancer Java :\n{ex}")
        else:
            messagebox.showerror("Erreur", "Choisis un .jar existant et une RAM d'au moins 512 Mo.")

    def envoyer(self, _):
        t = self.cmd.get().strip()
        if t and self.srv.actif:
            self.srv.commande(t)
            self.historique.append(t)
            self.pos_h = len(self.historique)
            self.cmd.set("")

    def naviguer(self, d):
        if self.historique:
            self.pos_h = max(0, min(len(self.historique), self.pos_h + d))
            self.cmd.set(self.historique[self.pos_h] if self.pos_h < len(self.historique) else "")

    def sauvegarde(self):
        if self.sauvegarde_en_cours or not self.dossier():
            return
        self.sauvegarde_en_cours = True
        self.bt_sauv.config(state="disabled")
        self.etat_b.config(text="Sauvegarde en cours…")
        threading.Thread(target=self._sauvegarder, args=(self.dossier(),), daemon=True).start()

    def _sauvegarder(self, dossier):  # les variables Tk ne se lisent que dans le thread principal
        actif = self.srv.actif
        try:
            if actif:  # fige les écritures pour avoir une copie cohérente
                self.srv.commande("save-off")
                self.srv.commande("save-all flush")
                time.sleep(4)
            msg = "Dernière sauvegarde : " + os.path.basename(sv.sauvegarder(dossier))
        except Exception as ex:
            msg = f"Échec de la sauvegarde : {ex}"
        finally:
            if actif:
                self.srv.commande("save-on")
        self.file.put(("sauvegarde", msg))

    def reset_auto(self):
        mn = int(self.auto.get()) if self.auto.get().isdigit() else 0
        self.prochaine_auto = time.time() + mn * 60 if mn else None

    def maj_mods(self):
        self.liste_m.delete(0, "end")
        if self.dossier():
            for n in sv.lister_mods(self.dossier()):
                self.liste_m.insert("end", n)

    def ajouter_mod(self):
        if not self.dossier():
            return messagebox.showerror("Erreur", "Choisis d'abord le .jar du serveur.")
        for p in filedialog.askopenfilenames(filetypes=[("Mods", "*.jar")]):
            sv.ajouter_mod(self.dossier(), p)
        self.maj_mods()

    def retirer_mod(self):
        noms = [self.liste_m.get(i) for i in self.liste_m.curselection()]
        if noms and messagebox.askyesno("Retirer", f"Supprimer {len(noms)} mod(s) du dossier mods ?"):
            for n in noms:
                sv.retirer_mod(self.dossier(), n)
            self.maj_mods()

    def importer_modpack(self):
        if not self.dossier():
            return messagebox.showerror("Erreur", "Choisis d'abord le .jar du serveur.")
        if self.srv.actif:
            return messagebox.showerror("Erreur", "Arrête le serveur avant d'importer un modpack.")
        p = filedialog.askopenfilename(filetypes=[("Modpack", "*.mrpack *.zip")])
        if not p:
            return
        self.bt_pack.config(state="disabled")
        self.onglets.select(0)
        self.log(f"[Modpack] Import de {os.path.basename(p)}…")
        threading.Thread(target=self._importer, args=(p, self.dossier()), daemon=True).start()

    def _importer(self, chemin, dossier):
        try:
            self.file.put(("modpack", mp.installer(chemin, dossier, self.file.put), dossier))
        except Exception as ex:
            self.file.put(("modpack", ex, dossier))

    def fin_modpack(self, info, dossier):
        self.bt_pack.config(state="normal")
        self.maj_mods()
        if isinstance(info, Exception):
            return messagebox.showerror("Modpack", f"Échec de l'import :\n{info}")
        l = [f"{info['installes']} mod(s) installé(s), {info['ignores']} client-only ignoré(s), {info['overrides']} fichier(s) de config copié(s)."]
        if info["echecs"]:
            l.append(f"{len(info['echecs'])} échec(s) :\n" + "\n".join(info["echecs"][:8]))
        if info.get("sauvegarde_mods"):
            l.append("Ancien dossier mods sauvegardé dans sauvegardes/.")
        if info["loader"]:
            l.append(f"Requis : {info['loader']} {info['loader_version']} pour Minecraft {info['mc']}.")
        self.log("[Modpack] " + " ".join(l[:1]))
        if info["loader"] == "fabric" and info["mc"] and messagebox.askyesno(
                "Modpack", "\n".join(l) + "\n\nTélécharger le serveur Fabric correspondant et l'utiliser ?"):
            try:
                self.jar.set(os.path.normpath(mp.installer_fabric(dossier, info["mc"], info["loader_version"])))
                self.log("[Modpack] Serveur Fabric prêt : fabric-server-launch.jar")
            except Exception as ex:
                messagebox.showerror("Fabric", f"Téléchargement impossible :\n{ex}")
        else:
            messagebox.showinfo("Modpack", "\n".join(l))

    # ---------- boucle ----------
    def boucle(self):
        try:
            while True:
                x = self.file.get_nowait()
                if isinstance(x, tuple) and x[0] == "modpack":
                    self.fin_modpack(x[1], x[2])
                elif isinstance(x, tuple):
                    self.sauvegarde_en_cours = False
                    self.bt_sauv.config(state="normal")
                    self.etat_b.config(text=x[1])
                else:
                    self.log(x)
        except queue.Empty:
            pass
        actif = self.srv.actif
        if not actif:
            self.arret_en_cours = False
        if self.arret_en_cours:
            self.bt.config(text="Arrêt…", state="disabled", style="Stop.TButton")
            self.point.config(fg=ORANGE)
            self.etat.config(text="Arrêt en cours")
        else:
            self.bt.config(text="Arrêter" if actif else "Démarrer", state="normal",
                           style="Stop.TButton" if actif else "Accent.TButton")
            self.point.config(fg=VERT if actif else ROUGE)
            self.etat.config(text="En marche" if actif else "Arrêté")
        joueurs = sorted(self.srv.joueurs)
        if list(self.liste_j.get(0, "end")) != joueurs:
            self.liste_j.delete(0, "end")
            for j in joueurs:
                self.liste_j.insert("end", j)
        self.nb_joueurs.config(text=f"{len(joueurs)} joueur(s)" if actif else "")
        if self.prochaine_auto and time.time() >= self.prochaine_auto:
            self.reset_auto()
            self.sauvegarde()
        self.after(200, self.boucle)

    def fermer(self):
        if self.srv.actif:
            if not messagebox.askyesno("Quitter", "Le serveur tourne : l'arrêter et quitter ?"):
                return
            self.title("Arrêt du serveur…")
            self.update()
            self.srv.arreter()
        self._enregistrer()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
