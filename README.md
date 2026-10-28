# 🚫 Bloqueur de comptes TikTok en masse

Un petit outil gratuit pour **bloquer d'un coup une liste de comptes TikTok** depuis votre propre compte, afin de ne plus voir leurs contenus ni interagir avec eux. Vous écrivez les pseudos dans un fichier texte, l'outil fait le reste.

> **Comment ça marche ?** L'outil ouvre un vrai navigateur (Chrome) et reproduit ce que vous feriez à la main : aller sur le profil → menu « … » → *Bloquer* → *Confirmer*. Il fait des pauses aléatoires pour ne pas ressembler à un robot.

---

## ⚠️ À lire avant de commencer

- **Utilisez uniquement votre propre compte**, avec vos propres listes.
- L'automatisation n'est pas prévue par TikTok : **ses conditions d'utilisation peuvent la restreindre**. Le risque principal est une limitation temporaire de votre compte. L'outil est volontairement lent et plafonné à **50 comptes par lancement** pour limiter ce risque. **Vous l'utilisez à vos risques.**
- **Vérifiez vos listes** : un pseudo mal copié peut bloquer la mauvaise personne.
- TikTok modifie souvent son site : l'outil peut avoir besoin d'une mise à jour (voir « Dépannage »).
- Le fichier `session_tiktok.json` donne accès à votre compte : **ne le partagez jamais**.

---

## 🧰 Étape 1 — Installer Python

### Sur Mac
1. Ouvrez l'application **Terminal** (Cmd + Espace, tapez « Terminal »).
2. Tapez `python3 --version` puis Entrée. Si un numéro s'affiche (3.9 ou plus), passez à l'étape 2.
3. Sinon, téléchargez Python sur **https://www.python.org/downloads/** et installez-le (double-clic, « Continuer » jusqu'au bout).

### Sur Windows
1. Téléchargez Python sur **https://www.python.org/downloads/**.
2. Lancez l'installeur et **cochez la case « Add python.exe to PATH »** (en bas de la première fenêtre), puis « Install Now ».
3. Ouvrez ensuite **Invite de commandes** (touche Windows, tapez « cmd »).

---

## 📦 Étape 2 — Préparer l'outil

1. Téléchargez ce projet et placez le dossier `tiktok-blocage-masse` où vous voulez (Bureau, par exemple).
2. Dans le Terminal / l'Invite de commandes, placez-vous dans le dossier :
   ```
   cd Desktop/tiktok-blocage-masse
   ```
   *(Astuce Mac : tapez `cd ` puis glissez le dossier dans la fenêtre du Terminal.)*
3. Créez un « environnement » propre (recommandé, à faire une seule fois) :
   - **Mac** :
     ```
     python3 -m venv venv
     source venv/bin/activate
     ```
   - **Windows** :
     ```
     python -m venv venv
     venv\Scripts\activate
     ```
   Vous devriez voir `(venv)` au début de la ligne.
4. Installez les composants nécessaires :
   ```
   pip install -r requirements.txt
   playwright install chromium
   ```
   Le second téléchargement (le navigateur) peut prendre quelques minutes.

---

## ✍️ Étape 3 — Remplir la liste

Ouvrez `comptes_a_bloquer.txt` avec le Bloc-notes / TextEdit et écrivez **un pseudo par ligne** :

```
@pseudo_un
pseudo.deux
https://www.tiktok.com/@pseudo_trois
```

- Le `@` est facultatif.
- Vous pouvez coller l'adresse du profil.
- Une ligne qui commence par `#` est ignorée (pratique pour les notes).
- Enregistrez le fichier.

---

## ▶️ Étape 4 — Lancer

```
python3 main.py        # Mac
python main.py         # Windows
```

### Au tout premier lancement
1. Une fenêtre de navigateur s'ouvre sur TikTok.
2. **Connectez-vous normalement** (téléphone, e-mail, QR code… comme d'habitude).
3. Quand vous voyez votre fil d'actualité, revenez dans le Terminal et **appuyez sur Entrée**.
4. Votre session est enregistrée : plus besoin de vous reconnecter ensuite.

### Ensuite
Le navigateur s'ouvre, l'outil traite les comptes un par un, et vous voyez :

```
[1/12] ✅ Compte @pseudo_un bloqué
[2/12] ☑️  Compte @pseudo.deux : déjà bloqué
[3/12] ❌ Erreur sur @pseudo_trois : bouton '...' introuvable sur le profil
```

**Laissez la fenêtre ouverte** et ne cliquez pas dedans pendant le travail. L'outil est lent *exprès* (quelques secondes entre chaque action, une pause plus longue tous les 10 comptes).

Vous pouvez arrêter à tout moment avec **Ctrl + C**. La progression est conservée : au prochain lancement, les comptes déjà traités sont sautés.

### Si TikTok affiche un captcha
L'outil se met en pause et vous alerte de 4 façons :
- un **son répété** toutes les 4 secondes ;
- une **notification Mac** en haut à droite ;
- un **gros bandeau rouge clignotant** en haut de la page TikTok (la fenêtre passe au premier plan) ;
- un message très visible dans le Terminal.

Résolvez le captcha dans le navigateur, puis appuyez sur Entrée dans le Terminal : le son s'arrête et le bandeau disparaît.
Pensez à **monter le volume** de votre Mac.

---

## 🔁 Les lancements suivants

À chaque fois, ouvrez le Terminal dans le dossier, puis :

```
source venv/bin/activate     # Mac   (Windows : venv\Scripts\activate)
python3 main.py              # Mac   (Windows : python main.py)
```

Si votre liste dépasse 50 comptes, relancez l'outil le lendemain pour la suite.

---

## 🛠️ Réglages (facultatif)

Tout en haut de `main.py`, section **RÉGLAGES** :

| Réglage | Rôle |
|---|---|
| `MAX_COMPTES_PAR_LANCEMENT` | Nombre max de comptes par lancement (50 par défaut) |
| `PAUSE_ENTRE_COMPTES` | Délai entre deux profils (en secondes) |
| `PAUSE_ENTRE_CLICS` | Délai entre deux clics |
| `PAUSE_LONGUE` / `PAUSE_LONGUE_TOUS_LES` | Pause « café » régulière |

Augmenter les pauses = plus lent, mais plus discret.

---

## 🩺 Dépannage

**« command not found: python3 » / « python n'est pas reconnu »**
Python n'est pas (bien) installé. Refaites l'étape 1 (sous Windows, pensez à cocher *Add to PATH*).

**« No module named playwright »**
Vous avez oublié d'activer l'environnement (`source venv/bin/activate`) ou d'exécuter `pip install -r requirements.txt`.

**« Executable doesn't exist » (Playwright)**
Lancez `playwright install chromium`.

**« Votre session a expiré »**
Normal de temps en temps : reconnectez-vous quand l'outil vous le demande. Vous pouvez aussi supprimer `session_tiktok.json` pour recommencer à zéro.

**Beaucoup de ❌ « bouton '...' introuvable » ou « option 'Bloquer' introuvable »**
TikTok a probablement modifié son site. Regardez les captures d'écran dans le dossier `captures_erreurs/`, puis ajustez les sélecteurs dans la section RÉGLAGES de `main.py` (ou ouvrez une *issue* sur le dépôt du projet).

**Mon compte est temporairement limité**
Arrêtez l'outil quelques jours, puis reprenez avec des pauses plus longues et moins de comptes par lancement.

---

## 🔒 Confidentialité

- Tout se passe **sur votre ordinateur** : aucun identifiant n'est envoyé ailleurs qu'à TikTok.
- Si vous publiez ce projet sur GitHub, le fichier `.gitignore` fourni empêche d'envoyer par erreur votre session et votre liste.

---

## 📄 Licence

Projet open-source : ajoutez le fichier de licence de votre choix (par exemple MIT) avant publication.