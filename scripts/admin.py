#!/usr/bin/env python3
"""Administration de la messagerie souveraine (Synapse + Keycloak).

Ce script ne fait AUCUNE cryptographie et ne touche à aucune clé E2EE.
Il gère uniquement les comptes : enrôlement, révocation, liste.

Authentification de l'administrateur auprès de Synapse (le mot de passe local de Synapse est désactivé
en mode oidc, pour que le second facteur ne soit pas contournable) :
  - par défaut : création d'un compte administrateur ÉPHÉMÈRE avec le secret d'enregistrement
    (lu dans le conteneur synapse, il faut donc lancer le script depuis le dossier du projet),
    désactivé à la fin de la commande ;
  - sinon, si ADMIN_USER et ADMIN_PASSWORD sont définis (mode de repli AUTH_MODE=password).

Variables : SYNAPSE_URL (http://127.0.0.1:8008), SERVER_NAME (localhost), AUTH_MODE (oidc),
REGISTRATION_SECRET, KEYCLOAK_URL (http://127.0.0.1:8081/auth), KEYCLOAK_REALM (souverain),
KEYCLOAK_ADMIN_USER (admin), KEYCLOAK_ADMIN_PASSWORD (valeur de démonstration).
"""
import argparse
import datetime
import getpass
import hashlib
import hmac
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SYNAPSE_URL", "http://127.0.0.1:8008").rstrip("/")
SERVER = os.environ.get("SERVER_NAME", "localhost")
AUTH_MODE = os.environ.get("AUTH_MODE", "oidc")
KC_URL = os.environ.get("KEYCLOAK_URL", "http://127.0.0.1:8081/auth").rstrip("/")
KC_REALM = os.environ.get("KEYCLOAK_REALM", "souverain")
KC_ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
KC_ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "Admin-KC-Demo-2026!")
EPHEMERAL_PREFIX = "cli."  # comptes techniques de ce script et des tests : masqués par « list »


class ApiError(Exception):
    pass


def http(method, url, token=None, body=None, form=None):
    """Requête HTTP. Retourne (statut, corps JSON, en-têtes). Lève ApiError en cas d'échec."""
    headers, data = {}, None
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {}), resp.headers
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:300]
        raise ApiError(f"HTTP {err.code} sur {method} {url} : {detail}")
    except urllib.error.URLError as err:
        raise ApiError(f"{url} injoignable : {err.reason}")


def call(method, path, token=None, body=None):
    """Appel de l'API de Synapse ; quitte le programme en cas d'erreur."""
    try:
        return http(method, BASE + path, token, body)[1]
    except ApiError as err:
        sys.exit(f"Erreur : {err}")


def mxid(user):
    return user if user.startswith("@") else f"@{user}:{SERVER}"


def localpart(user):
    return user.lstrip("@").split(":")[0]


def q(user):
    return urllib.parse.quote(mxid(user), safe="")


# ---------------------------------------------------------------- session administrateur Synapse

def registration_secret():
    secret = os.environ.get("REGISTRATION_SECRET")
    if secret:
        return secret.strip()
    try:
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "synapse", "cat", "/generated/registration_secret"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as err:
        sys.exit(f"Impossible de lire le secret d'enregistrement : {err}")
    if out.returncode != 0 or not out.stdout.strip():
        sys.exit("Secret d'enregistrement introuvable : lancez le script depuis le dossier du projet "
                 "(pile démarrée) ou définissez REGISTRATION_SECRET.")
    return out.stdout.strip()


def register_with_secret(name, admin=False):
    """Crée un compte avec le secret d'enregistrement (HMAC-SHA1, protocole de Synapse) et retourne son jeton.

    Le jeton est un jeton ordinaire (avec appareil) : la désactivation du compte l'invalide.
    """
    secret = registration_secret()
    nonce = call("GET", "/_synapse/admin/v1/register")["nonce"]
    password = "Aa1!" + secrets.token_urlsafe(24)
    mac = hmac.new(secret.encode(), digestmod=hashlib.sha1)
    for part in (nonce, name, password):
        mac.update(part.encode())
        mac.update(b"\x00")
    mac.update(b"admin" if admin else b"notadmin")
    res = call("POST", "/_synapse/admin/v1/register", body={
        "nonce": nonce, "username": name, "password": password, "admin": admin, "mac": mac.hexdigest()})
    return res["access_token"]


def open_admin_session():
    """Retourne (jeton, fonction_de_fermeture)."""
    user, password = os.environ.get("ADMIN_USER"), os.environ.get("ADMIN_PASSWORD")
    if user and password:
        res = call("POST", "/_matrix/client/v3/login", body={
            "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user},
            "password": password, "initial_device_display_name": "admin-cli"})
        token = res["access_token"]

        def close():
            try:
                http("POST", BASE + "/_matrix/client/v3/logout", token, {})
            except ApiError:
                pass
        return token, close

    # Compte administrateur éphémère, créé avec le secret d'enregistrement.
    name = EPHEMERAL_PREFIX + "admin." + secrets.token_hex(4)
    token = register_with_secret(name, admin=True)

    def close():
        try:
            http("POST", f"{BASE}/_synapse/admin/v1/deactivate/{urllib.parse.quote(mxid(name), safe='')}",
                 token, {"erase": False})
        except ApiError:
            pass
    return token, close


# ---------------------------------------------------------------- Keycloak

def kc_token():
    _, body, _ = http("POST", f"{KC_URL}/realms/master/protocol/openid-connect/token", form={
        "grant_type": "password", "client_id": "admin-cli",
        "username": KC_ADMIN_USER, "password": KC_ADMIN_PASSWORD})
    return body["access_token"]


def kc_find(token, username):
    _, users, _ = http("GET", f"{KC_URL}/admin/realms/{KC_REALM}/users?username="
                       f"{urllib.parse.quote(username)}&exact=true", token)
    return users[0] if users else None


def kc_disable(username):
    """Désactive l'utilisateur dans Keycloak et ferme ses sessions. Retourne True si fait."""
    try:
        token = kc_token()
        user = kc_find(token, username)
        if not user:
            print("  Keycloak : utilisateur introuvable (rien à désactiver)")
            return False
        user["enabled"] = False
        http("PUT", f"{KC_URL}/admin/realms/{KC_REALM}/users/{user['id']}", token, user)
        http("POST", f"{KC_URL}/admin/realms/{KC_REALM}/users/{user['id']}/logout", token, {})
        print("  Keycloak : compte désactivé et sessions fermées")
        return True
    except ApiError as err:
        print(f"  Keycloak : NON mis à jour ({err})")
        return False


# ---------------------------------------------------------------- commandes

def cmd_enroll(args, token):
    name = args.name or args.user
    password = args.password or getpass.getpass(f"Mot de passe initial pour {mxid(args.user)} : ")
    if AUTH_MODE == "password":
        call("PUT", f"/_synapse/admin/v2/users/{q(args.user)}", token, {
            "password": password, "displayname": name,
            "admin": args.role == "admin", "deactivated": False})
        print(f"Enrôlé : {mxid(args.user)} (rôle : {args.role}, mode repli sans second facteur)")
        return

    # Mode oidc : l'agent est créé dans Keycloak ; il devra changer son mot de passe et configurer son
    # application TOTP à la première connexion.
    first, _, last = name.partition(" ")
    try:
        kc = kc_token()
        http("POST", f"{KC_URL}/admin/realms/{KC_REALM}/users", kc, {
            "username": localpart(args.user), "enabled": True,
            "firstName": first, "lastName": last or "-",
            "email": f"{localpart(args.user)}@souverain.local", "emailVerified": True,
            "requiredActions": ["UPDATE_PASSWORD", "CONFIGURE_TOTP"],
            "credentials": [{"type": "password", "value": password, "temporary": True}]})
    except ApiError as err:
        sys.exit(f"Création dans Keycloak impossible : {err}")
    # Compte Matrix créé à l'avance (et marqué administrateur si besoin) ; rattaché à Keycloak à la première connexion.
    call("PUT", f"/_synapse/admin/v2/users/{q(args.user)}", token, {
        "displayname": name, "admin": args.role == "admin", "deactivated": False})
    print(f"Enrôlé : {mxid(args.user)} (rôle : {args.role}). Première connexion : changement du mot de passe "
          "et configuration du code TOTP obligatoires.")


def cmd_list(args, token):
    # deactivated=true : inclure les comptes révoqués (masqués par défaut par Synapse).
    res = call("GET", "/_synapse/admin/v2/users?limit=200&guests=false&deactivated=true", token)
    for u in res.get("users", []):
        if u["name"].split(":")[0].lstrip("@").startswith(EPHEMERAL_PREFIX):
            continue  # comptes techniques éphémères de ce script
        etat = "REVOQUE" if u.get("deactivated") else "actif"
        role = "admin" if u.get("admin") else "agent"
        print(f"{u['name']:40} {role:6} {etat}")


def cmd_devices(args, token):
    res = call("GET", f"/_synapse/admin/v2/users/{q(args.user)}/devices", token)
    for d in res.get("devices", []):
        print(f"{d['device_id']:15} {d.get('display_name') or '-':30} dernière IP : {d.get('last_seen_ip') or '-'}")
    print(f"{len(res.get('devices', []))} appareil(s)")


def cmd_revoke(args, token):
    target = mxid(args.user)
    horodatage = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    before = call("GET", f"/_synapse/admin/v2/users/{q(args.user)}/devices", token).get("devices", [])
    print(f"[{horodatage}] Révocation de {target} : {len(before)} appareil(s) avant")

    # Mode oidc : on coupe d'abord l'identité (plus aucune reconnexion possible), puis l'accès à Matrix.
    kc_done = True
    if AUTH_MODE == "oidc" and not os.environ.get("SKIP_KEYCLOAK"):
        kc_done = kc_disable(localpart(args.user))

    # Désactive le compte : invalide tous les jetons, supprime les appareils, retire des salles.
    call("POST", f"/_synapse/admin/v1/deactivate/{q(args.user)}", token, {"erase": False})

    # Vérifications : ne rien déclarer révoqué sans l'avoir contrôlé.
    # Synapse retire l'agent des salles en tâche de fond : on attend la confirmation (20 s maximum).
    # Les jetons sont déjà invalides à ce stade ; le départ des salles déclenche le changement de clés des autres clients.
    for _ in range(20):
        info = call("GET", f"/_synapse/admin/v2/users/{q(args.user)}", token)
        after = call("GET", f"/_synapse/admin/v2/users/{q(args.user)}/devices", token).get("devices", [])
        rooms = call("GET", f"/_synapse/admin/v1/users/{q(args.user)}/joined_rooms", token).get("joined_rooms", [])
        if info.get("deactivated") and not after and not rooms:
            break
        time.sleep(1)

    ok = True
    print(f"  compte désactivé : {info.get('deactivated')}")
    print(f"  appareils restants : {len(after)}")
    print(f"  salles encore jointes : {len(rooms)}")
    if not info.get("deactivated") or after or rooms:
        ok = False
    if ok:
        print("REVOCATION VERIFIEE : accès serveur coupé sur tous les appareils.")
    else:
        sys.exit("REVOCATION INCOMPLETE : voir les compteurs ci-dessus.")
    if not kc_done:
        print("ATTENTION : l'identité Keycloak n'a PAS été désactivée ; le compte Matrix reste bloqué, "
              "mais désactivez aussi l'utilisateur dans Keycloak.")
    print("Rappel : ce qu'un appareil a déjà déchiffré reste lisible sur cet appareil.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("enroll", help="enrôler un agent")
    e.add_argument("user")
    e.add_argument("--name")
    e.add_argument("--password")
    e.add_argument("--role", choices=["agent", "admin"], default="agent")
    e.set_defaults(fn=cmd_enroll)
    sub.add_parser("list", help="lister les comptes").set_defaults(fn=cmd_list)
    d = sub.add_parser("devices", help="lister les appareils d'un agent")
    d.add_argument("user")
    d.set_defaults(fn=cmd_devices)
    r = sub.add_parser("revoke", help="révoquer un agent sur tous ses appareils")
    r.add_argument("user")
    r.set_defaults(fn=cmd_revoke)
    args = p.parse_args()

    token, close = open_admin_session()
    try:
        args.fn(args, token)
    finally:
        close()


if __name__ == "__main__":
    main()
