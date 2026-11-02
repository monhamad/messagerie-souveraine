#!/usr/bin/env python3
"""Scénarios automatisés contre un Synapse en marche (par défaut http://127.0.0.1:8008).

Prérequis : la pile est démarrée et les comptes de demo/comptes-demo.csv existent.
Usage : python3 tests/test_api_scenarios.py
ATTENTION : le test révoque agent.demo2 et verrouille temporairement agent.demo3 (test anti brute-force).
Pour le rejouer : recréer la pile (docker compose down -v && docker compose up -d).
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("SYNAPSE_URL", "http://127.0.0.1:8008")
SERVER = os.environ.get("SERVER_NAME", "localhost")
ADMIN_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "admin.py")
PW = "Agent-Demo-2026!"
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


def login(user, pw):
    return req("POST", "/_matrix/client/v3/login", body={
        "type": "m.login.password", "identifier": {"type": "m.id.user", "user": user}, "password": pw})


def admin(*args):
    env = dict(os.environ, ADMIN_USER="admin.demo", ADMIN_PASSWORD="Admin-Demo-2026!", SERVER_NAME=SERVER)
    return subprocess.run(["python3", "-I", ADMIN_SCRIPT, *args], capture_output=True, text=True, env=env)


def main():
    st, body = req("POST", "/_matrix/client/v3/register", body={
        "username": "intrus.demo", "password": "Intrus-Demo-2026!", "auth": {"type": "m.login.dummy"}})
    check("Intrus : inscription publique refusée", st == 403, f"HTTP {st} {json.dumps(body)[:120]}")
    st, body = login("intrus.demo", "Intrus-Demo-2026!")
    check("Intrus : connexion d'un compte non enrôlé refusée", st in (401, 403), f"HTTP {st} {body.get('errcode')}")

    st1, a1 = login("agent.demo1", PW)
    st2, a2 = login("agent.demo2", PW)
    check("Agents démo enrôlés : connexion OK", st1 == 200 and st2 == 200, f"HTTP {st1}/{st2}")
    t1, t2 = a1["access_token"], a2["access_token"]

    st, room = req("POST", "/_matrix/client/v3/createRoom", t1, {
        "name": "Test groupe", "preset": "private_chat", "invite": [f"@agent.demo2:{SERVER}"]})
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

    st, who = req("GET", "/_matrix/client/v3/account/whoami", t2)
    check("Avant révocation : le jeton de agent.demo2 est valide", st == 200, f"HTTP {st}")
    r = admin("revoke", "agent.demo2")
    print(r.stdout.strip())
    check("admin.py revoke vérifié", r.returncode == 0 and "REVOCATION VERIFIEE" in r.stdout,
          f"rc={r.returncode} {r.stderr.strip()[:150]}")
    st, who = req("GET", "/_matrix/client/v3/account/whoami", t2)
    check("Après révocation : l'ancien jeton est rejeté", st == 401, f"HTTP {st} {who.get('errcode')}")
    st, body = login("agent.demo2", PW)
    check("Après révocation : reconnexion impossible", st in (401, 403), f"HTTP {st} {body.get('errcode')}")
    st, _ = req("PUT", f"/_matrix/client/v3/rooms/{rid_q}/send/m.room.message/tx1", t2, {"msgtype": "m.text", "body": "x"})
    check("Après révocation : envoi dans le groupe impossible", st == 401, f"HTTP {st}")
    st, mem = req("GET", f"/_matrix/client/v3/rooms/{rid_q}/state/m.room.member/%40agent.demo2%3A{SERVER}", t1)
    check("Après révocation : agent.demo2 a quitté le groupe", st == 200 and mem.get("membership") in ("leave", "ban"),
          f"HTTP {st} membership={mem.get('membership')}")
    st, _ = req("GET", "/_matrix/client/v3/account/whoami", t1)
    check("Les autres agents ne sont pas affectés", st == 200, f"HTTP {st}")

    r = admin("enroll", "agent.nouveau", "--password", "Nouveau-Agent-2026!", "--name", "Agent Nouveau")
    check("admin.py enroll crée un agent", r.returncode == 0, r.stdout.strip() or r.stderr.strip()[:150])
    st, _ = login("agent.nouveau", "Nouveau-Agent-2026!")
    check("Agent enrôlé par script peut se connecter", st == 200, f"HTTP {st}")
    r = admin("list")
    ligne = [l for l in r.stdout.splitlines() if f"agent.demo2:{SERVER}" in l]
    check("admin.py list affiche agent.demo2 comme REVOQUE", ligne and "REVOQUE" in ligne[0], ligne[0] if ligne else "absent")

    codes = [login("agent.demo3", "Mauvais-Mot-2026!")[0] for _ in range(10)]
    check("Brute-force : le compte est limité (429) après des échecs répétés", 429 in codes, f"codes HTTP : {codes}")

    failed = [n for n, ok in results if not ok]
    print(f"\n=== {len(results) - len(failed)}/{len(results)} vérifications réussies ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
