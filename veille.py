"""Mode veille : écoute le port du serveur éteint ; un ping affiche un message, une connexion réveille le serveur."""
import json, socket, struct, threading


def _varint(s):
    n = 0
    for i in range(5):
        b = s.recv(1)
        if not b:
            raise EOFError
        n |= (b[0] & 0x7F) << (7 * i)
        if not b[0] & 0x80:
            return n
    raise ValueError("varint trop long")


def _encode(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _paquet(id_, data):
    corps = _encode(id_) + data
    return _encode(len(corps)) + corps


def _chaine(t):
    b = t.encode("utf-8")
    return _encode(len(b)) + b


def _lire_paquet(s):
    n = _varint(s)
    if not 0 < n <= 4096:
        raise ValueError("paquet invalide")
    buf = b""
    while len(buf) < n:
        part = s.recv(n - len(buf))
        if not part:
            raise EOFError
        buf += part
    return buf


class Veille:
    def __init__(self, port, sur_reveil):
        self.port, self.sur_reveil = port, sur_reveil
        self.demarrage = False  # vrai une fois le réveil demandé
        self.sock = None

    @property
    def active(self):
        return self.sock is not None

    def ouvrir(self):
        if self.sock:
            return
        self.demarrage = False
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", self.port))
        s.listen(5)
        self.sock = s
        threading.Thread(target=self._accepter, args=(s,), daemon=True).start()

    def fermer(self):
        s, self.sock = self.sock, None
        if s:
            s.close()

    def _accepter(self, s):
        while True:
            try:
                c, _ = s.accept()
            except OSError:  # socket fermé
                return
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    def _client(self, c):
        try:
            c.settimeout(5)
            p = _lire_paquet(c)  # poignée de main : id, protocole, adresse, port, état
            i = 1
            proto = 0
            for k in range(5):
                proto |= (p[i] & 0x7F) << (7 * k)
                i += 1
                if not p[i - 1] & 0x80:
                    break
            etat = p[-1]
            if etat == 1:  # ping de la liste de serveurs
                _lire_paquet(c)
                texte = "Serveur en démarrage…" if self.demarrage else "Serveur en veille — connecte-toi pour le démarrer"
                j = {"version": {"name": "Veille", "protocol": proto}, "players": {"max": 0, "online": 0},
                     "description": {"text": texte}}
                c.sendall(_paquet(0, _chaine(json.dumps(j))))
                c.sendall(_paquet(1, _lire_paquet(c)[1:]))  # écho du ping
            elif etat == 2:  # connexion : on réveille le serveur
                _lire_paquet(c)  # démarrage de connexion du joueur ; sans lecture, la fermeture ferait un RST
                self.demarrage = True
                c.sendall(_paquet(0, _chaine(json.dumps({"text": "Le serveur démarre, reconnecte-toi dans une minute."}))))
                self.sur_reveil()
        except (OSError, EOFError, ValueError, IndexError, struct.error):
            pass
        finally:
            c.close()
