import os, threading, tkinter as tk
from tkinter import filedialog, messagebox, ttk
import serveur as sv

BG, FG, CHAMP, ACCENT = "#1e1e24", "#e6e6e6", "#2b2b33", "#4f8cff"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion serveur Minecraft")
        self.geometry("980x640")
        self.configure(bg=BG)
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=CHAMP)
        s.configure("TButton", background=CHAMP, padding=5)
        s.map("TButton", background=[("active", ACCENT)])
        s.configure("TNotebook", background=BG)
        s.configure("TNotebook.Tab", background=CHAMP, foreground=FG, padding=(12, 4))
        s.map("TNotebook.Tab", background=[("selected", ACCENT)])
        self.srv = sv.Serveur(lambda l: self.after(0, self.log, l))
        self.java = tk.StringVar(value=sv.java_par_defaut())
        self.jar = tk.StringVar()
        self.ram = tk.StringVar(value="2048")
        self.auto = tk.StringVar(value="0")
        self.cmd = tk.StringVar()
        self.tick = 0
        self._construire()
        self.protocol("WM_DELETE_WINDOW", self.fermer)
        self.after(1000, self.rafraichir)

    def _construire(self):
        haut = ttk.Frame(self)
        haut.pack(fill="x", padx=8, pady=6)
        for i, (txt, var, w) in enumerate([("Java", self.java, 30), (".jar", self.jar, 40), ("RAM (Mo)", self.ram, 6)]):
            ttk.Label(haut, text=txt).grid(row=0, column=i * 2, padx=3)
            ttk.Entry(haut, textvariable=var, width=w).grid(row=0, column=i * 2 + 1)
        ttk.Button(haut, text="Choisir .jar", command=self.choisir_jar).grid(row=1, column=0, pady=4)
        self.bt = ttk.Button(haut, text="Démarrer", command=self.basculer)
        self.bt.grid(row=1, column=1, sticky="w")
        self.etat = ttk.Label(haut, text="Arrêté")
        self.etat.grid(row=1, column=3, sticky="w")
        onglets = ttk.Notebook(self)
        onglets.pack(fill="both", expand=True, padx=8, pady=4)
        # Console
        c = ttk.Frame(onglets)
        onglets.add(c, text="Console")
        self.console = tk.Text(c, bg="#111", fg="#ddd", state="disabled", wrap="none")
        self.console.pack(fill="both", expand=True)
        e = ttk.Entry(c, textvariable=self.cmd)
        e.pack(fill="x")
        e.bind("<Return>", self.envoyer)
        # Joueurs
        j = ttk.Frame(onglets)
        onglets.add(j, text="Joueurs")
        self.liste_j = tk.Listbox(j, bg=CHAMP, fg=FG)
        self.liste_j.pack(fill="both", expand=True)
        # Sauvegardes
        b = ttk.Frame(onglets)
        onglets.add(b, text="Sauvegardes")
        ttk.Button(b, text="Sauvegarder maintenant", command=self.sauvegarde).pack(pady=8)
        f = ttk.Frame(b)
        f.pack()
        ttk.Label(f, text="Auto toutes les (minutes, 0 = non) :").pack(side="left")
        ttk.Entry(f, textvariable=self.auto, width=5).pack(side="left")
        self.etat_b = ttk.Label(b, text="")
        self.etat_b.pack(pady=8)
        # Mods
        m = ttk.Frame(onglets)
        onglets.add(m, text="Mods")
        self.liste_m = tk.Listbox(m, bg=CHAMP, fg=FG, selectmode="extended")
        self.liste_m.pack(fill="both", expand=True)
        bm = ttk.Frame(m)
        bm.pack()
        ttk.Button(bm, text="Ajouter…", command=self.ajouter_mod).pack(side="left", padx=4, pady=4)
        ttk.Button(bm, text="Retirer", command=self.retirer_mod).pack(side="left", padx=4)

    def dossier(self):
        return os.path.dirname(self.jar.get()) if self.jar.get() else None

    def log(self, l):
        self.console.config(state="normal")
        self.console.insert("end", l + "\n")
        self.console.see("end")
        self.console.config(state="disabled")

    def choisir_jar(self):
        p = filedialog.askopenfilename(filetypes=[("Jar", "*.jar")])
        if p:
            self.jar.set(p)
            self.maj_mods()

    def basculer(self):
        if self.srv.actif:
            self.bt.config(state="disabled")
            threading.Thread(target=self.srv.arreter, daemon=True).start()
        elif os.path.isfile(self.jar.get()) and self.ram.get().isdigit():
            try:
                self.srv.demarrer(self.java.get(), self.jar.get(), int(self.ram.get()))
            except OSError as ex:
                messagebox.showerror("Erreur", str(ex))
        else:
            messagebox.showerror("Erreur", "Choisis un .jar et une RAM valide.")

    def envoyer(self, _):
        self.srv.commande(self.cmd.get())
        self.cmd.set("")

    def sauvegarde(self):
        if self.srv.actif:
            self.srv.commande("save-all flush")
            self.after(3000, self.sauvegarde_zip)
        else:
            self.sauvegarde_zip()

    def sauvegarde_zip(self):
        try:
            p = sv.sauvegarder(self.dossier())
            self.etat_b.config(text=f"Dernière sauvegarde : {os.path.basename(p)}")
        except Exception as ex:
            self.etat_b.config(text=f"Échec : {ex}")

    def maj_mods(self):
        self.liste_m.delete(0, "end")
        if self.dossier():
            for n in sv.lister_mods(self.dossier()):
                self.liste_m.insert("end", n)

    def ajouter_mod(self):
        if not self.dossier():
            return messagebox.showerror("Erreur", "Choisis d'abord le .jar.")
        for p in filedialog.askopenfilenames(filetypes=[("Mods", "*.jar")]):
            sv.ajouter_mod(self.dossier(), p)
        self.maj_mods()

    def retirer_mod(self):
        for i in self.liste_m.curselection():
            sv.retirer_mod(self.dossier(), self.liste_m.get(i))
        self.maj_mods()

    def rafraichir(self):
        actif = self.srv.actif
        self.bt.config(text="Arrêter" if actif else "Démarrer", state="normal")
        self.etat.config(text="En marche" if actif else "Arrêté")
        self.liste_j.delete(0, "end")
        for j in sorted(self.srv.joueurs):
            self.liste_j.insert("end", j)
        self.tick += 1
        mn = int(self.auto.get()) if self.auto.get().isdigit() else 0
        if mn and self.dossier() and self.tick % (mn * 60) == 0:
            self.sauvegarde()
        self.after(1000, self.rafraichir)

    def fermer(self):
        self.srv.arreter()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
