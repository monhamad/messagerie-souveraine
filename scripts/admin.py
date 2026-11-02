#!/usr/bin/env python3
"""Administration de la messagerie souveraine via l'API d'administration de Synapse.

Ce script ne fait AUCUNE cryptographie et ne touche à aucune clé E2EE.
Il gère uniquement les comptes : enrôlement, révocation, liste.

Variables d'environnement : SYNAPSE_URL (défaut http://127.0.0.1:8008), SERVER_NAME (défaut localhost),
ADMIN_USER, ADMIN_PASSWORD (sinon demandés).
"""
import argparse
import datetime
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SYNAPSE_URL", "http://127.0.0.1:8008").rstrip("/")
SERVER = os.environ.get("SERVER_NAME", "localhost")


def call(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")
        sys.exit(f"Erreur HTTP {err.code} sur {method} {path} : {detail}")
    except urllib.error.URLError as err:
        sys.exit(f"Synapse injoignable sur {BASE} : {err.reason}")


def mxid(user):
    return user if user.startswith("@") else f"@{user}:{SERVER}"


def admin_login():
    user = os.environ.get("ADMIN_USER") or input("Compte administrateur : ")
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Mot de passe : ")
    res = call("POST", "/_matrix/client/v3/login", body={
        "type": "m.login.password",
        "identifier": {"type": "m.id.user", "user": user},
        "password": password,
        "initial_device_display_name": "admin-cli",
    })
    return res["access_token"]


def admin_logout(token):
    try:
        call("POST", "/_matrix/client/v3/logout", token=token, body={})
    except SystemExit:
        pass


def q(user):
    return urllib.parse.quote(mxid(user), safe="")


def cmd_enroll(args, token):
    password = args.password or getpass.getpass(f"Mot de passe initial pour {mxid(args.user)} : ")
    call("PUT", f"/_synapse/admin/v2/users/{q(args.user)}", token, {
        "password": password,
        "displayname": args.name or args.user,
        "admin": args.role == "admin",
        "deactivated": False,
    })
    print(f"Enrôlé : {mxid(args.user)} (rôle : {args.role})")


def cmd_list(args, token):
    # deactivated=true : inclure les comptes révoqués (masqués par défaut par Synapse).
    res = call("GET", "/_synapse/admin/v2/users?limit=200&guests=false&deactivated=true", token)
    for u in res.get("users", []):
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

    token = admin_login()
    try:
        args.fn(args, token)
    finally:
        admin_logout(token)


if __name__ == "__main__":
    main()
