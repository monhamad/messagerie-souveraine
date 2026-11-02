# Messagerie souveraine de l'administration

Prototype de messagerie instantanée chiffrée de bout en bout pour les agents publics burkinabè, hébergeable sur l'infrastructure de l'État. Sprint technique pré-hackathon 2026 (MTDPCE/DGTD).

**État du prototype** : socle Matrix durci et scripts d'administration écrits ; l'enrôlement, la révocation et l'inscription fermée ont été testés sur un vrai Synapse (voir `docs/TESTS.md`). L'authentification à deux facteurs (Keycloak/TOTP) n'est **pas encore intégrée**. [À METTRE À JOUR avant le dépôt.]

## Concept

Les agents échangent messages, groupes et fichiers dans une interface web simple (Element), avec chiffrement de bout en bout. Le serveur appartient à l'administration, n'a aucune dépendance à un service externe et ne peut pas lire les messages. Un administrateur enrôle les agents et peut les révoquer d'un seul ordre.

## Architecture

Navigateur → Caddy (TLS interne) → Element Web (interface) ou Synapse (serveur Matrix) → PostgreSQL. Le chiffrement est réalisé dans le navigateur par les bibliothèques officielles de Matrix (Olm/Megolm). Détails : `docs/ARCHITECTURE.md`.

## Technologies et licences

Licences à vérifier sur chaque dépôt officiel avant dépôt.

| Technologie | Licence | Projet |
|---|---|---|
| Synapse | AGPL-3.0 | https://github.com/element-hq/synapse |
| Element Web | AGPL-3.0 / GPL-3.0 / commerciale | https://github.com/element-hq/element-web |
| PostgreSQL | PostgreSQL License | https://www.postgresql.org |
| Caddy | Apache-2.0 | https://github.com/caddyserver/caddy |
| Alpine Linux | MIT et licences diverses | https://alpinelinux.org |
| Notre code (scripts, configuration) | MIT | ce dépôt |

**Niveau d'engagement : Étendre et adapter** (configuration, durcissement et administration de Matrix/Synapse et Element). Aucune cryptographie n'est développée par l'équipe.

## Installation

Prérequis : Docker et Docker Compose, accès à un registre d'images à l'installation (ensuite aucun service externe n'est nécessaire).

```
docker compose up -d
```

Ouvrir `https://localhost` (accepter le certificat de l'autorité interne). Comptes de démonstration **fictifs** dans `demo/comptes-demo.csv` : `admin.demo`, `agent.demo1`, `agent.demo2`, `agent.demo3`, `chef.demo`.

Arrêt : `docker compose down`. Sauvegarde et restauration : `scripts/backup.sh`, `scripts/restore.sh`.

## Administration

```
ADMIN_USER=admin.demo python3 scripts/admin.py enroll nom.agent --role agent
ADMIN_USER=admin.demo python3 scripts/admin.py revoke nom.agent
python3 scripts/admin.py list
```

`revoke` désactive le compte, supprime les appareils et les jetons, retire l'agent des salles (les autres clients renouvellent alors les clés du groupe) et vérifie le résultat.

## Tests

`python3 tests/test_api_scenarios.py` (intrus, salle chiffrée par défaut, révocation, anti brute-force) et `tests/check_no_plaintext.sh` (absence de clair en base).

## Limites connues

- La révocation coupe l'accès au serveur ; elle **n'efface pas** ce qu'un appareil a déjà déchiffré.
- Le serveur voit toujours qui échange avec qui, quand, et la taille des messages (réduit, pas supprimé).
- Pas de notifications push mobiles (elles dépendraient d'un service tiers).
- Application web uniquement ; pas d'application mobile native.
- Aucun audit de sécurité externe.
