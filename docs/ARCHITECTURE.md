# Architecture et matrice de conformité

> Statut au 1er novembre 2026. Légende : **Écrit** = fichier produit, **non exécuté** sur une vraie pile Docker ; **À faire** = pas encore commencé ; **Vérifié** = exécuté avec preuve (aucun pour l'instant, voir `docs/TESTS.md`).

## 1. Choix du protocole : Matrix (Olm/Megolm)

| Critère | Matrix (Synapse + Element) | Signal (libsignal) | MLS (OpenMLS) | XMPP + OMEMO |
|---|---|---|---|---|
| Serveur auto-hébergeable sans tiers | Oui, mature | Difficile : Signal-Server dépend de SMS, push et stockage cloud | Bibliothèque seule, serveur à écrire | Oui (Prosody, ejabberd) |
| Client prêt à l'emploi avec E2EE, groupes, fichiers, multi-appareils | **Oui (Element Web)** | Clients liés au service Signal | Non, tout est à construire | Clients inégaux, groupes OMEMO fragiles |
| Gestion des appareils et des sessions | Oui (API admin Synapse) | Partielle | À construire | Partielle |
| Maturité et documentation | Élevée | Élevée (protocole) | Moyenne | Moyenne |
| Faisabilité en un sprint | **Oui** | Non | Non | Moyenne |

**Décision** : Matrix, niveau d'engagement **« Étendre et adapter »** (configuration et durcissement de Synapse et d'Element, scripts d'administration). Aucune cryptographie n'est écrite par l'équipe : le chiffrement est fait côté client par les bibliothèques officielles de Matrix.

## 2. Composants

| Composant | Rôle | Licence (à vérifier sur le dépôt officiel avant de la déclarer) |
|---|---|---|
| Synapse | Serveur Matrix, ne stocke que du chiffré pour les salles E2EE | AGPL-3.0 |
| PostgreSQL | Base de Synapse | PostgreSQL License |
| Element Web | Client web (E2EE côté navigateur) | AGPL-3.0 / GPL-3.0 / commerciale (double licence, à confirmer) |
| Caddy | Reverse proxy, TLS interne, en-têtes de sécurité | Apache-2.0 |
| Alpine | Conteneur d'initialisation (génère les secrets et la config) | Licences diverses (MIT pour la base) |
| `scripts/admin.py` (notre code) | Enrôlement, révocation, audit via l'API admin | MIT |
| Keycloak | Identité et second facteur TOTP, relié à Synapse par OIDC ; le mot de passe local de Synapse est désactivé | Apache-2.0 |

Flux : navigateur → Caddy (TLS) → Element (fichiers statiques) ou Synapse (API Matrix). Les messages sont chiffrés dans le navigateur avant envoi ; Synapse les stocke dans PostgreSQL sous forme d'évènements `m.room.encrypted`. Les fichiers sont chiffrés côté client avant l'envoi vers le dépôt de médias.

## 3. Matrice de conformité

| # | Exigence (source : cahier des charges) | Réponse prévue | Statut |
|---|---|---|---|
| 1 | E2EE messages et fichiers, protocole éprouvé | Matrix Olm/Megolm, `encryption_enabled_by_default_for_room_type: all` | Écrit, non exécuté |
| 2 | Aucune cryptographie maison | Aucun code crypto dans le dépôt | Par construction ; à contrôler à la relecture |
| 3 | Installation en une commande | `docker compose up -d` (init, db, synapse, bootstrap, element, caddy) | Écrit, non exécuté |
| 4 | Aucun service tiers indispensable | Fédération et serveurs de clés désactivés, pas d'aperçu d'URL, pas de push, TLS interne | Partiel : les images Docker sont téléchargées à l'installation (question posée au jury) |
| 5 | Seuls des agents enrôlés | Inscription publique fermée, comptes créés par l'administrateur | Écrit, non exécuté |
| 6 | Authentification forte (second facteur) | Keycloak + OIDC + TOTP imposé ; connexion par mot de passe Matrix désactivée | Écrit. **Testé** : Synapse n'offre que le SSO. **Non testé** : page de connexion Keycloak et saisie du code TOTP (à valider sur Docker) |
| 7 | Gestion des rôles | Administrateur serveur + niveaux de puissance des salles | Partiel |
| 8 | Révocation immédiate sur tous les appareils | `admin.py revoke` : désactivation, jetons et appareils supprimés, vérification | Écrit, non exécuté |
| 9 | Le serveur ne lit rien | `tests/check_no_plaintext.sh` (base et médias) + capture réseau | Écrit, non exécuté |
| 10 | Métadonnées documentées et réduites | Voir section 4 | Documenté ici, note de sécurité **à faire** |
| 11 | Note de sécurité (2 pages) | À rédiger après les tests réels | **À faire** |
| 12 | LICENSE à la racine | MIT (notre code) | Écrit |
| 13 | Technologies citées avec licence et lien | Tableau section 2 et README | À finaliser |
| 14 | Niveau d'engagement déclaré | Étendre et adapter | Écrit |
| 15 | Dépôt public avec commits progressifs | À créer par l'équipe | **À faire** (ne jamais antidater) |
| 16 | README.md français (2 pages) | Fourni | Écrit |
| 17 | Comptes de démonstration fictifs | `demo/comptes-demo.csv` | Écrit |
| 18 | Vidéo de 3 minutes | Scénario dans `docs/DEMO.md` | **À faire** (à enregistrer par vous) |
| 19 | Fiche équipe et attestations 2026-2027 | Hors code | À faire par l'équipe |
| 20 | Épreuve « intrus » | Inscription fermée + test | Écrit, non exécuté |
| 21 | Épreuve « explication du code » | Chaque membre doit pouvoir expliquer la config E2EE et `admin.py` | Humain, non délégable |
| Bonus | Tests automatisés (+2), langue nationale (+3), contribution amont (+5) | Tests : scripts ; les deux autres non garantis | Partiel / non prévu |

## 4. Métadonnées vues par le serveur

Le serveur voit toujours : identités des comptes, appartenance aux salles, horodatage et taille de chaque évènement, type d'évènement, noms et identifiants d'appareils, adresse IP et agent utilisateur des connexions, profil (nom, avatar), accusés de lecture, taille des fichiers.

Mesures de réduction retenues : fédération désactivée, présence désactivée, aperçus d'URL désactivés, contenu absent des notifications, logs d'accès coupés (niveau WARNING), `user_ips_max_age: 7d`, accès aux profils réservé aux utilisateurs authentifiés. Ces mesures **réduisent** l'exposition sans l'éliminer.

## 5. Risques et points critiques

- **Fuite en clair** (salle non chiffrée, notification, sauvegarde) : éliminatoire. Test obligatoire sur votre machine.
- **Révocation** : bloque l'accès au serveur et déclenche le changement de clés par les clients. Elle n'efface pas ce qu'un appareil a déjà déchiffré.
- **2FA à valider sur la pile réelle** : la moitié Keycloak (page de connexion, TOTP) n'a pas pu être testée hors de Docker. En cas d'échec, le mode de repli `AUTH_MODE=password` fonctionne mais **sans second facteur** : à déclarer comme tel.
- **Dépendance forte à Keycloak** : s'il est arrêté, plus personne ne peut se connecter (le mot de passe Matrix est désactivé).
- **Versions d'images non épinglées** : épingler après le premier démarrage réussi.
- **Explication orale** : élimination si un membre ne sait pas expliquer.

## 6. Calendrier réaliste (journée du 1er novembre, échéance à confirmer)

| Créneau | Travail |
|---|---|
| 0-2 h | `docker compose up -d` sur votre machine, correction des erreurs, 2 navigateurs qui s'écrivent |
| 2-4 h | Tests : absence de clair, intrus, révocation. Remplir `docs/TESTS.md` avec les vrais résultats |
| 4-6 h | Keycloak + TOTP si la pile est stable ; sinon déclarer la limite |
| 6-8 h | Note de sécurité, note de pré-projet, README final |
| 8-9 h | Vidéo (3 min), dépôt public, dépôt de la candidature |

## 7. Répartition (3 étudiants)

- **A, infrastructure et sécurité** : Compose, durcissement, tests de non-clair, 2FA.
- **B, client et usages** : Element, annuaire, innovation démontrable, démo.
- **C, documentation et révocation** : notes, README, `admin.py`, vidéo, préparation de l'entretien.

Chacun doit pouvoir expliquer le chiffrement et l'authentification.
