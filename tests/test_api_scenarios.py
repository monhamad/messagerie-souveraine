#!/usr/bin/env python3
"""Scénarios automatisés contre un Synapse en marche (par défaut http://127.0.0.1:8008).

Prérequis : la pile est démarrée (docker compose up -d), les comptes de demo/comptes-demo.csv existent,
et le script est lancé DEPUIS LE DOSSIER DU PROJET (il lit le secret d'enregistrement dans le conteneur).
Usage : python3 tests/test_api_scenarios.py
Variables : AUTH_MODE (oidc par défaut), SKIP_KEYCLOAK=1 si Keycloak n'est pas joignable.

Le test de révocation utilise des comptes techniques jetables (préfixe « cli. ») pour ne pas consommer les
comptes de démonstration : il peut être rejoué sans recréer la pile.
Seul le test avec Keycloak (enrôlement puis révocation de « agent.nouveau ») ne peut être rejoué qu'une fois
par pile : docker compose down -v && docker compose up -d
"""
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "scripts")
sys.path.insert(0, SCRIPTS)
import admin as adm  # noqa: E402  (scripts/admin.py)

BASE = adm.BASE
SERVER = adm.SERVER
AUTH_MODE = adm.AUTH_MODE
SKIP_KC = bool(os.environ.get("SKIP_KEYCLOAK"))
DEMO_ACCOUNTS = ["admin.demo", "agent.demo1", "agent.demo2", "agent.demo3", "chef.demo"]
results = []


def req(method, path, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw.decode(errors="replace")[:200]}


def check(name, cond, proof):
    results.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}\n       preuve : {proof}")


def admin_cli(*args):
    return subprocess.run(["python3", "-I", os.path.join(SCRIPTS, "admin.py"), *args],
                          capture_output=True, text=True, env=dict(os.environ))


def main():
    admin_token, close = adm.open_admin_session()
    try:
        run(admin_token)
    finally:
        close()
    failed = [n for n, ok in results if not ok]
    print(f"\n=== {len(results) - len(failed)}/{len(results)} vérifications réussies (mode {AUTH_MODE}) ===")
    return 1 if failed else 0


def run(admin_token):
    # --- Authentification forte ------------------------------------------------
    st, flows = req("GET", "/_matrix/client/v3/login")
    types = [f.get("type") for f in flows.get("flows", [])]
    if AUTH_MODE == "oidc":
        check("2FA : la connexion par mot de passe local est DESACTIVEE (pas de contournement)",
              st == 200 and "m.login.password" not in types, f"méthodes de connexion offertes : {types}")
        check("2FA : la seule connexion offerte passe par Keycloak (SSO)", "m.login.sso" in types,
              json.dumps(flows)[:200])
    else:
        check("Mode repli : connexion par mot de passe (sans second facteur)", "m.login.password" in types, str(types))

    # --- Intrus : compte non enrôlé -------------------------------------------
    st, body = req("POST", "/_matrix/client/v3/register", body={
        "username": "intrus.demo", "password": "Intrus-Demo-2026!", "auth": {"type": "m.login.dummy"}})
    check("Intrus : inscription publique refusée", st == 403, f"HTTP {st} {json.dumps(body)[:120]}")
    st, body = req("POST", "/_matrix/client/v3/login", body={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": "intrus.demo"},
        "password": "Intrus-Demo-2026!"})
    check("Intrus : connexion par mot de passe refusée", st in (400, 401, 403), f"HTTP {st} {body.get('errcode')}")

    # --- Comptes de démonstration présents ------------------------------------
    missing = [u for u in DEMO_ACCOUNTS
               if req("GET", f"/_synapse/admin/v2/users/{adm.q(u)}", admin_token)[0] != 200]
    check("Comptes de démonstration créés par le conteneur bootstrap", not missing,
          "tous présents" if not missing else f"absents : {missing}")

    # --- Conversation de groupe entre deux comptes techniques jetables --------
    suffix = secrets.token_hex(3)
    sender, revoked = f"cli.test.a.{suffix}", f"cli.test.b.{suffix}"
    t1 = adm.register_with_secret(sender)
    t2 = adm.register_with_secret(revoked)
    st, room = req("POST", "/_matrix/client/v3/createRoom", t1, {
        "name": "Test groupe", "preset": "private_chat", "invite": [f"@{revoked}:{SERVER}"]})
    rid = room.get("room_id")
    check("Création d'une salle de groupe", st == 200 and rid, f"HTTP {st} room_id={rid}")
    rid_q = rid.replace("!", "%21").replace(":", "%3A")
    st, enc = req("GET", f"/_matrix/client/v3/rooms/{rid_q}/state/m.room.encryption", t1)
    check("Salle chiffrée par défaut (m.room.encryption présent)",
          st == 200 and enc.get("algorithm") == "m.megolm.v1.aes-sha2", f"HTTP {st} {json.dumps(enc)}")
    st, _ = req("POST", f"/_matrix/client/v3/rooms/{rid_q}/join", t2, {})
    check("Agent invité rejoint le groupe", st == 200, f"HTTP {st}")

    st, _ = req("GET", "/_matrix/federation/v1/version")
    check("Fédération : point d'entrée absent", st == 404, f"HTTP {st}")

    # --- Révocation pendant la conversation -----------------------------------
    st, _ = req("GET", "/_matrix/client/v3/account/whoami", t2)
    check("Avant révocation : le jeton de l'agent est valide", st == 200, f"HTTP {st}")
    r = admin_cli("revoke", revoked)
    print(r.stdout.strip())
    check("admin.py revoke vérifié", r.returncode == 0 and "REVOCATION VERIFIEE" in r.stdout,
          f"rc={r.returncode} {r.stderr.strip()[:150]}")
    st, who = req("GET", "/_matrix/client/v3/account/whoami", t2)
    check("Après révocation : l'ancien jeton est rejeté", st == 401, f"HTTP {st} {who.get('errcode')}")
    st, _ = req("PUT", f"/_matrix/client/v3/rooms/{rid_q}/send/m.room.message/tx1", t2,
                {"msgtype": "m.text", "body": "x"})
    check("Après révocation : envoi dans le groupe impossible", st == 401, f"HTTP {st}")
    st, mem = req("GET", f"/_matrix/client/v3/rooms/{rid_q}/state/m.room.member/@{revoked}:{SERVER}".replace(
        "@", "%40").replace(":" + SERVER, "%3A" + SERVER), t1)
    check("Après révocation : l'agent a quitté le groupe", st == 200 and mem.get("membership") in ("leave", "ban"),
          f"HTTP {st} membership={mem.get('membership')}")
    st, _ = req("GET", "/_matrix/client/v3/account/whoami", t1)
    check("Les autres agents ne sont pas affectés", st == 200, f"HTTP {st}")

    # --- Enrôlement et révocation avec Keycloak (pile Docker complète) --------
    if AUTH_MODE == "oidc" and SKIP_KC:
        print("[SKIP] Enrôlement et révocation via Keycloak : SKIP_KEYCLOAK défini")
    else:
        r = admin_cli("enroll", "agent.nouveau", "--password", "Nouveau-Agent-2026!", "--name", "Agent Nouveau")
        check("admin.py enroll crée l'agent (Keycloak en mode oidc)", r.returncode == 0,
              r.stdout.strip() or r.stderr.strip()[:200])
        if AUTH_MODE == "oidc":
            r = admin_cli("revoke", "agent.nouveau")
            check("Révocation : l'identité Keycloak est aussi désactivée",
                  r.returncode == 0 and "Keycloak : compte désactivé" in r.stdout, r.stdout.strip()[-250:])

    r = admin_cli("list")
    ligne = [l for l in r.stdout.splitlines() if f"{revoked}:{SERVER}" in l]
    check("admin.py list masque les comptes techniques jetables « cli. »",
          not ligne and "cli." not in r.stdout, "aucune ligne cli.*" if "cli." not in r.stdout else r.stdout[:200])
    if AUTH_MODE == "oidc" and not SKIP_KC:
        ligne = [l for l in r.stdout.splitlines() if "agent.nouveau" in l]
        check("admin.py list affiche agent.nouveau comme REVOQUE", ligne and "REVOQUE" in ligne[0],
              ligne[0] if ligne else "absent")


if __name__ == "__main__":
    sys.exit(main())
