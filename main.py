#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bloqueur de comptes TikTok en masse
===================================

Lit une liste de pseudos dans `comptes_a_bloquer.txt` et bloque chaque compte
depuis VOTRE compte TikTok, en pilotant un vrai navigateur (Playwright).

Fonctionnement :
  1. Premier lancement : un navigateur s'ouvre, vous vous connectez à TikTok
     à la main, la session est enregistrée dans `session_tiktok.json`.
  2. Lancements suivants : la session est réutilisée automatiquement.
  3. Pour chaque pseudo : visite du profil -> menu "..." -> Bloquer -> Confirmer,
     avec des pauses aléatoires pour imiter un comportement humain.
  4. Les comptes déjà traités sont mémorisés (`comptes_deja_traites.txt`) :
     vous pouvez relancer l'outil sans refaire le travail.

⚠️ TikTok modifie régulièrement son site. Si un blocage échoue systématiquement,
   les "sélecteurs" (section RÉGLAGES ci-dessous) sont à ajuster.
"""

import os
import platform
import random
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

# ============================================================================
# RÉGLAGES (modifiables sans risque)
# ============================================================================

DOSSIER = Path(__file__).resolve().parent
FICHIER_COMPTES = DOSSIER / "comptes_a_bloquer.txt"
FICHIER_SESSION = DOSSIER / "session_tiktok.json"
FICHIER_TRAITES = DOSSIER / "comptes_deja_traites.txt"
DOSSIER_ERREURS = DOSSIER / "captures_erreurs"

# Pauses aléatoires (en secondes) : (minimum, maximum)
PAUSE_ENTRE_CLICS = (1.5, 4.0)       # entre deux clics / actions
PAUSE_ENTRE_COMPTES = (8.0, 20.0)    # entre deux pages de profil
PAUSE_LONGUE = (60.0, 120.0)         # petite "pause café" régulière
PAUSE_LONGUE_TOUS_LES = 10           # une pause longue tous les N comptes

# Plafond par lancement : mieux vaut aller doucement pour éviter les restrictions.
MAX_COMPTES_PAR_LANCEMENT = 50

# --- Sélecteurs et textes (français + anglais) ---
# Si TikTok change son site, c'est ici qu'il faut intervenir.
SEL_TITRE_PROFIL = '[data-e2e="user-title"]'
SEL_BOUTON_PLUS = '[data-e2e="user-more"]'               # bouton "..." du profil
SEL_BOUTON_CONFIRMER = '[data-e2e="block-popup-block-btn"]'
SEL_BOUTON_CONNEXION = '[data-e2e="top-login-button"]'   # visible si NON connecté
SEL_CAPTCHA = '#captcha-verify-container-main-page, .captcha_verify_container, [class*="captcha"]'

RE_BLOQUER = re.compile(r"^\s*(Bloquer|Block)\s*$", re.I)
RE_DEBLOQUER = re.compile(r"^\s*(D[ée]bloquer|Unblock)\s*$", re.I)
RE_INTROUVABLE = re.compile(r"(Impossible de trouver ce compte|Couldn.?t find this account)", re.I)

# Un pseudo TikTok : lettres, chiffres, point, underscore (max 24 caractères)
RE_PSEUDO = re.compile(r"^[A-Za-z0-9._]{1,24}$")


# ============================================================================
# OUTILS DE BASE
# ============================================================================

def pause(plage):
    """Attend un temps aléatoire compris dans `plage` (min, max) secondes."""
    time.sleep(random.uniform(*plage))


def normaliser_pseudo(ligne):
    """
    Nettoie une ligne du fichier et renvoie un pseudo propre, ou None.
    Accepte : "pseudo", "@pseudo", "https://www.tiktok.com/@pseudo?lang=fr"
    """
    ligne = ligne.strip()
    if not ligne or ligne.startswith("#"):
        return None
    # Adresse de profil collée en entier ?
    correspondance = re.search(r"tiktok\.com/@([A-Za-z0-9._]+)", ligne)
    if correspondance:
        ligne = correspondance.group(1)
    ligne = ligne.lstrip("@").strip()
    return ligne if RE_PSEUDO.match(ligne) else ""


def lire_comptes():
    """Lit le fichier texte et renvoie la liste des pseudos (sans doublons)."""
    if not FICHIER_COMPTES.exists():
        FICHIER_COMPTES.write_text(
            "# Un pseudo TikTok par ligne (avec ou sans @)\n", encoding="utf-8"
        )
        print(f"📝 Le fichier {FICHIER_COMPTES.name} n'existait pas : je viens de le créer.")
        print("   Ajoutez-y des pseudos, puis relancez l'outil.")
        sys.exit(0)

    pseudos, vus = [], set()
    for numero, ligne in enumerate(FICHIER_COMPTES.read_text(encoding="utf-8").splitlines(), 1):
        pseudo = normaliser_pseudo(ligne)
        if pseudo is None:
            continue
        if pseudo == "":
            print(f"⚠️  Ligne {numero} ignorée (pseudo invalide) : {ligne.strip()!r}")
            continue
        if pseudo.lower() not in vus:
            vus.add(pseudo.lower())
            pseudos.append(pseudo)
    return pseudos


def lire_deja_traites():
    if not FICHIER_TRAITES.exists():
        return set()
    return {l.strip().lower() for l in FICHIER_TRAITES.read_text(encoding="utf-8").splitlines() if l.strip()}


def marquer_traite(pseudo):
    with open(FICHIER_TRAITES, "a", encoding="utf-8") as f:
        f.write(pseudo + "\n")


# ============================================================================
# SESSION (connexion manuelle une seule fois)
# ============================================================================

def a_un_cookie_de_session(context):
    return any(c["name"] in ("sessionid", "sessionid_ss") for c in context.cookies())


def sauvegarder_session(context):
    context.storage_state(path=str(FICHIER_SESSION))
    try:
        os.chmod(FICHIER_SESSION, 0o600)  # lisible uniquement par vous (Mac/Linux)
    except OSError:
        pass


def premiere_connexion(playwright):
    """Ouvre TikTok, laisse l'utilisateur se connecter, puis sauvegarde la session."""
    print("\n🔐 PREMIÈRE CONNEXION")
    print("   Une fenêtre de navigateur va s'ouvrir sur TikTok.")
    print("   1) Connectez-vous à VOTRE compte (comme d'habitude).")
    print("   2) Une fois sur votre fil d'actualité, revenez ici et appuyez sur Entrée.\n")

    navigateur = playwright.chromium.launch(headless=False)
    context = navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 850})
    page = context.new_page()
    page.goto("https://www.tiktok.com/login")

    while True:
        input("👉 Connecté ? Appuyez sur Entrée ici... ")
        if a_un_cookie_de_session(context):
            break
        print("❌ Connexion non détectée. Terminez la connexion dans le navigateur, puis réessayez.")

    sauvegarder_session(context)
    navigateur.close()
    print("✅ Session enregistrée : les prochains lancements seront automatiques.\n")


def est_connecte(page):
    """Vérifie que la session est encore valide (pas de bouton 'Se connecter')."""
    page.goto("https://www.tiktok.com/", wait_until="domcontentloaded")
    pause((3.0, 5.0))
    try:
        return not page.locator(SEL_BOUTON_CONNEXION).first.is_visible()
    except PlaywrightError:
        return True  # en cas de doute, on continue


# ============================================================================
# BLOCAGE D'UN COMPTE
# ============================================================================

def captcha_present(page):
    try:
        return page.locator(SEL_CAPTCHA).first.is_visible()
    except PlaywrightError:
        return False


# JavaScript injecté dans la page : gros bandeau rouge clignotant tout en haut.
JS_AFFICHER_BANDEAU = """
() => {
  if (document.getElementById('alerte-captcha')) return;
  const style = document.createElement('style');
  style.id = 'alerte-captcha-style';
  style.textContent = '@keyframes clignote {0%,100%{opacity:1} 50%{opacity:.35}}';
  document.head.appendChild(style);
  const bandeau = document.createElement('div');
  bandeau.id = 'alerte-captcha';
  bandeau.textContent = '🚨 CAPTCHA : résolvez-le ici, puis revenez au Terminal et appuyez sur Entrée 🚨';
  bandeau.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;' +
    'background:#e60023;color:#fff;font:bold 26px sans-serif;text-align:center;' +
    'padding:22px;animation:clignote 1s infinite;box-shadow:0 4px 20px rgba(0,0,0,.5);';
  document.body.appendChild(bandeau);
  document.title = '🚨 CAPTCHA À RÉSOUDRE';
}
"""

JS_RETIRER_BANDEAU = """
() => {
  for (const id of ['alerte-captcha', 'alerte-captcha-style']) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }
}
"""


def jouer_son():
    """Fait du bruit pour attirer l'attention (Mac, Windows ou Linux)."""
    try:
        systeme = platform.system()
        if systeme == "Darwin":  # Mac
            subprocess.run(["afplay", "/System/Library/Sounds/Sosumi.aiff"], check=False)
        elif systeme == "Windows":
            import winsound
            for _ in range(3):
                winsound.Beep(1000, 300)
        else:
            print("\a", end="", flush=True)
    except Exception:
        print("\a", end="", flush=True)  # "bip" du terminal en dernier recours


def notification_systeme(titre, message):
    """Notification native du Mac (en haut à droite de l'écran)."""
    if platform.system() == "Darwin":
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'display notification "{message}" with title "{titre}" sound name "Glass"'],
                check=False,
            )
        except Exception:
            pass


def _alarme_repetee(arret):
    """Rejoue le son toutes les 4 secondes tant que le captcha n'est pas résolu."""
    while not arret.is_set():
        jouer_son()
        arret.wait(4)


def gerer_captcha(page):
    """
    Si TikTok affiche un captcha : alerte sonore répétée + notification +
    bandeau rouge dans le navigateur + message dans le terminal,
    puis attente que l'utilisateur le résolve.
    """
    if not captcha_present(page):
        return

    print("\n" + "🚨" * 20)
    print("🧩 CAPTCHA ! TikTok demande une vérification.")
    print("   👉 Allez dans la fenêtre du navigateur et résolvez-la.")
    print("🚨" * 20 + "\a")

    notification_systeme("🧩 Captcha TikTok", "Résolvez-le dans le navigateur puis revenez au Terminal.")
    try:
        page.bring_to_front()
        page.evaluate(JS_AFFICHER_BANDEAU)
    except PlaywrightError:
        pass

    arret = threading.Event()
    threading.Thread(target=_alarme_repetee, args=(arret,), daemon=True).start()
    try:
        input("   Une fois le captcha résolu, appuyez sur Entrée ici... ")
    finally:
        arret.set()
        try:
            page.evaluate(JS_RETIRER_BANDEAU)
        except PlaywrightError:
            pass
    pause(PAUSE_ENTRE_CLICS)


def attendre_profil(page, delai=15):
    """Attend que le profil s'affiche. Renvoie 'ok', 'introuvable', 'captcha' ou 'timeout'."""
    fin = time.time() + delai
    while time.time() < fin:
        if captcha_present(page):
            return "captcha"
        if page.locator(SEL_TITRE_PROFIL).first.is_visible():
            return "ok"
        if page.get_by_text(RE_INTROUVABLE).first.is_visible():
            return "introuvable"
        time.sleep(0.5)
    return "timeout"


def chercher_dans_menu(page, delai=6):
    """Après ouverture du menu '...', cherche 'Bloquer' (ou 'Débloquer' = déjà bloqué)."""
    fin = time.time() + delai
    while time.time() < fin:
        if page.get_by_text(RE_DEBLOQUER).first.is_visible():
            return "deja", None
        element = page.get_by_text(RE_BLOQUER).first
        if element.is_visible():
            return "bloquer", element
        time.sleep(0.4)
    return None, None


def confirmer_blocage(page, delai=6):
    """Clique sur le bouton 'Bloquer' de la fenêtre de confirmation."""
    candidats = [
        page.locator(SEL_BOUTON_CONFIRMER),
        page.locator('[role="dialog"]').get_by_role("button", name=RE_BLOQUER),
        page.get_by_role("button", name=RE_BLOQUER),
    ]
    fin = time.time() + delai
    while time.time() < fin:
        for candidat in candidats:
            if candidat.first.is_visible():
                candidat.first.click()
                return True
        time.sleep(0.4)
    return False


def bloquer_compte(page, pseudo):
    """
    Bloque un compte. Renvoie (statut, message) avec statut parmi :
    'bloque', 'deja', 'introuvable', 'erreur'.
    """
    page.goto(f"https://www.tiktok.com/@{pseudo}", wait_until="domcontentloaded")
    pause(PAUSE_ENTRE_CLICS)

    etat = attendre_profil(page)
    if etat == "captcha":
        gerer_captcha(page)
        etat = attendre_profil(page)
    if etat == "introuvable":
        return "introuvable", "compte introuvable (pseudo modifié ou supprimé ?)"
    if etat != "ok":
        return "erreur", "la page du profil ne s'est pas chargée"

    # 1) Ouvrir le menu "..."
    bouton_plus = page.locator(SEL_BOUTON_PLUS).first
    if not bouton_plus.is_visible():
        return "erreur", "bouton '...' introuvable sur le profil"
    bouton_plus.hover()
    pause((0.5, 1.2))
    bouton_plus.click()
    pause(PAUSE_ENTRE_CLICS)
    gerer_captcha(page)

    # 2) Trouver "Bloquer" dans le menu
    resultat, element = chercher_dans_menu(page)
    if resultat == "deja":
        page.keyboard.press("Escape")
        return "deja", "déjà bloqué"
    if resultat is None:
        return "erreur", "option 'Bloquer' introuvable dans le menu"
    element.click()
    pause(PAUSE_ENTRE_CLICS)

    # 3) Confirmer
    if not confirmer_blocage(page):
        return "erreur", "fenêtre de confirmation introuvable"
    pause(PAUSE_ENTRE_CLICS)
    gerer_captcha(page)

    # 4) Contrôle : la fenêtre de confirmation doit avoir disparu
    if page.locator(SEL_BOUTON_CONFIRMER).first.is_visible():
        return "erreur", "la confirmation semble être restée ouverte"
    return "bloque", "bloqué"


def capture_erreur(page, pseudo):
    """Enregistre une capture d'écran pour aider au dépannage."""
    try:
        DOSSIER_ERREURS.mkdir(exist_ok=True)
        page.screenshot(path=str(DOSSIER_ERREURS / f"{pseudo}.png"))
    except PlaywrightError:
        pass


# ============================================================================
# PROGRAMME PRINCIPAL
# ============================================================================

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # emojis corrects sous Windows
    except AttributeError:
        pass

    print("=" * 60)
    print("   BLOQUEUR DE COMPTES TIKTOK EN MASSE")
    print("=" * 60)

    comptes = lire_comptes()
    deja = lire_deja_traites()
    a_faire = [c for c in comptes if c.lower() not in deja]

    if not comptes:
        print("\nℹ️  Aucun pseudo dans comptes_a_bloquer.txt. Ajoutez-en puis relancez.")
        return
    print(f"\n📋 {len(comptes)} compte(s) dans la liste, {len(comptes) - len(a_faire)} déjà traité(s).")
    if not a_faire:
        print("🎉 Rien à faire : tous les comptes ont déjà été traités.")
        return
    if len(a_faire) > MAX_COMPTES_PAR_LANCEMENT:
        print(f"🛡️  Pour limiter les risques, seuls {MAX_COMPTES_PAR_LANCEMENT} comptes seront traités "
              f"aujourd'hui. Relancez l'outil plus tard (idéalement demain) pour la suite.")
        a_faire = a_faire[:MAX_COMPTES_PAR_LANCEMENT]

    bilan = {"bloque": 0, "deja": 0, "introuvable": 0, "erreur": 0}

    with sync_playwright() as playwright:
        if not FICHIER_SESSION.exists():
            premiere_connexion(playwright)

        navigateur = playwright.chromium.launch(headless=False)
        context = navigateur.new_context(
            storage_state=str(FICHIER_SESSION),
            locale="fr-FR",
            viewport={"width": 1280, "height": 850},
        )
        page = context.new_page()
        page.set_default_timeout(10_000)

        try:
            if not est_connecte(page):
                print("\n⚠️  Votre session a expiré. Reconnexion nécessaire.")
                navigateur.close()
                FICHIER_SESSION.unlink(missing_ok=True)
                premiere_connexion(playwright)
                navigateur = playwright.chromium.launch(headless=False)
                context = navigateur.new_context(
                    storage_state=str(FICHIER_SESSION),
                    locale="fr-FR",
                    viewport={"width": 1280, "height": 850},
                )
                page = context.new_page()
                page.set_default_timeout(10_000)

            print("\n🚀 C'est parti ! (Ctrl+C pour arrêter à tout moment)\n")
            total = len(a_faire)

            for i, pseudo in enumerate(a_faire, 1):
                prefixe = f"[{i}/{total}]"
                try:
                    statut, message = bloquer_compte(page, pseudo)
                except PlaywrightError as e:
                    statut, message = "erreur", f"problème technique ({str(e).splitlines()[0][:80]})"

                bilan[statut] += 1
                if statut == "bloque":
                    print(f"{prefixe} ✅ Compte @{pseudo} bloqué")
                    marquer_traite(pseudo)
                elif statut == "deja":
                    print(f"{prefixe} ☑️  Compte @{pseudo} : déjà bloqué")
                    marquer_traite(pseudo)
                elif statut == "introuvable":
                    print(f"{prefixe} ❓ Compte @{pseudo} : {message}")
                    marquer_traite(pseudo)
                else:
                    print(f"{prefixe} ❌ Erreur sur @{pseudo} : {message}")
                    capture_erreur(page, pseudo)

                if i < total:
                    if i % PAUSE_LONGUE_TOUS_LES == 0:
                        print("   ☕ Petite pause pour rester discret...")
                        pause(PAUSE_LONGUE)
                    else:
                        pause(PAUSE_ENTRE_COMPTES)

            sauvegarder_session(context)  # rafraîchit les cookies

        except KeyboardInterrupt:
            print("\n\n⏹️  Arrêt demandé. Votre progression est sauvegardée.")
        finally:
            navigateur.close()

    print("\n" + "=" * 60)
    print("   BILAN")
    print("=" * 60)
    print(f"   ✅ Bloqués        : {bilan['bloque']}")
    print(f"   ☑️  Déjà bloqués   : {bilan['deja']}")
    print(f"   ❓ Introuvables   : {bilan['introuvable']}")
    print(f"   ❌ Erreurs        : {bilan['erreur']}")
    if bilan["erreur"]:
        print("\n   Les comptes en erreur seront retentés au prochain lancement.")
        print(f"   Captures d'écran disponibles dans : {DOSSIER_ERREURS.name}/")


if __name__ == "__main__":
    main()