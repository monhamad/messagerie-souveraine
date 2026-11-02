# Tests : ce qui a réellement été exécuté

Règle : un test n'est marqué « Exécuté » que s'il a tourné avec un résultat observé. Les colonnes « Observé » des tests non exécutés sont **à remplir par l'équipe** sur sa machine.

## Environnement des tests déjà exécutés (1er novembre 2026)

- Synapse **1.164.1** installé par `pip` (pas l'image Docker), base **SQLite** (pas PostgreSQL), Python 3.13.
- Configuration : celle du projet, rendue par `config/init/init.sh`. Seuls la base, les chemins et l'adresse d'écoute ont été adaptés.
- **Non couvert** : pile Docker, Caddy, Element Web, PostgreSQL, chiffrement réel de messages et de fichiers par un client.
- Commande rejouable sur la pile Docker : `python3 tests/test_api_scenarios.py` (18 vérifications).

## Les 10 scénarios obligatoires

| # | Scénario | Statut | Observé / preuve |
|---|---|---|---|
| 1 | Deux agents échangent des messages | **Non exécuté** | Nécessite deux navigateurs avec Element. À faire. |
| 2 | Fichier envoyé chiffré | **Non exécuté** | À faire avec Element ; vérifier ensuite avec `tests/check_no_plaintext.sh`. |
| 3 | Le serveur ne lit rien | **Partiel** | Exécuté : toute salle créée contient `m.room.encryption` (megolm) sans action de l'utilisateur. Non exécuté : inspection de la base PostgreSQL et du trafic après envoi de vrais messages. |
| 4 | Agent non enrôlé refusé | **Exécuté** | Inscription : HTTP 403 `Registration has been disabled`. Connexion : HTTP 403 `M_FORBIDDEN`. |
| 5 | Intrus tente de rejoindre un groupe | **Partiel** | Un compte non enrôlé ne peut pas s'authentifier (test 4), donc pas d'accès à l'API. Un test dédié « agent enrôlé non invité » n'est pas écrit. |
| 6 | Révocation pendant une conversation | **Exécuté (API)** | `admin.py revoke` : 2 appareils supprimés, compte désactivé, 0 salle jointe, `membership=leave`. Non testé avec les clients Element ouverts. |
| 7 | Agent révoqué tente de recevoir/envoyer | **Exécuté** | Ancien jeton : HTTP 401 `M_UNKNOWN_TOKEN`. Reconnexion : 403. Envoi dans le groupe : 401. |
| 8 | Plusieurs appareils | **Partiel** | La révocation a supprimé 2 appareils d'un même agent. Pas de test de synchronisation E2EE multi-appareils. |
| 9 | Redémarrage du serveur | **Non exécuté** | À faire : `docker compose restart`, puis reconnexion et lecture de l'historique. |
| 10 | Fonctionnement sans service tiers | **Non exécuté** | À faire : couper l'accès Internet de la machine après `docker compose pull`, puis tout rejouer. |

## Vérifications supplémentaires exécutées

| Vérification | Résultat |
|---|---|
| Fédération désactivée | `/_matrix/federation/v1/version` : HTTP 404 |
| Anti brute-force par compte | 5 échecs (403) puis HTTP 429 |
| `admin.py enroll` / `list` | Agent créé et connecté ; `list` affiche les révoqués |

## Défauts trouvés et corrigés grâce aux tests

1. `admin.py revoke` concluait « incomplet » à tort : Synapse retire l'agent des salles en arrière-plan. Le script attend maintenant la confirmation (20 s maximum).
2. Limite de connexions par adresse IP trop stricte pour une administration derrière un NAT : relâchée, la protection brute-force reste par compte.
3. `admin.py list` masquait les comptes révoqués : corrigé.

## À exécuter sur votre machine avant le dépôt

1. `docker compose up -d` depuis un dossier vierge, puis `docker compose logs bootstrap`.
2. Ouvrir `https://localhost` (accepter le certificat interne) avec deux navigateurs ou profils, connecter `agent.demo1` et `agent.demo2`, créer un groupe, échanger un message contenant un marqueur (ex. `TESTCLAIR-12345`) et un fichier.
3. `tests/check_no_plaintext.sh TESTCLAIR-12345` : doit afficher « OK ».
4. Capture réseau (Wireshark/tcpdump) : le trafic doit être en TLS, aucun marqueur lisible.
5. `python3 tests/test_api_scenarios.py` sur une pile neuve.
6. Noter les résultats observés dans ce fichier.

## Résultats observés sur la pile Docker réelle (2 novembre 2026)

Environnement : Ubuntu (VM), Docker Compose, Synapse + PostgreSQL + Element Web + Caddy, images officielles.

| Scénario | Résultat observé |
|---|---|
| 1. Deux agents échangent des messages | **Exécuté** : agent.demo1 et agent.demo2 échangent dans une discussion chiffrée (Element affiche « Envoyer un message chiffré »). |
| 2. Fichier envoyé chiffré | **Exécuté** : `test-secret.txt` (39 octets, contenant TESTFICHIER-98765) envoyé ; 1 fichier stocké dans `/data/media_store`. |
| 3. Le serveur ne lit rien | **Exécuté** : `tests/check_no_plaintext.sh` : 0 `m.room.message`, 2 `m.room.encrypted` ; marqueurs TESTCLAIR-12345 et TESTFICHIER-98765 introuvables dans `event_json` et dans le dépôt de médias. |
| 4. Agent non enrôlé | **Exécuté** (API, voir plus haut) |
| 6. Révocation pendant une conversation | **Exécuté** : `admin.py revoke agent.demo2` : compte désactivé, 0 appareil, 0 salle. Fenêtre d'agent.demo2 : « Appareil supprimé : par mesure de sécurité, la session a expiré ». Fenêtre d'agent.demo1 : « agent.demo2 a quitté le salon ». |
| 7. Agent révoqué | **Exécuté** : reconnexion refusée (« Nom d'utilisateur et/ou mot de passe incorrect »). Message générique de Synapse, qui ne révèle pas l'état du compte. |

Non vérifié directement : le changement des clés du groupe après le départ de l'agent révoqué. Il est effectué par les clients Element, pas par le serveur. Le serveur coupe l'accès, ce qui est testé.

Toujours **non exécutés** : 8 (multi-appareils E2EE), 9 (redémarrage du serveur), 10 (fonctionnement sans Internet), capture réseau.

| 9. Redémarrage du serveur | **Exécuté** : `docker compose restart` ; après rechargement, la session d'agent.demo1 est conservée.  historique visible, clé de récupération non redemandée. |
