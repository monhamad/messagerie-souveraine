# Guide de défense devant le jury

Règle d'or : **ne dites jamais plus que ce que vous avez vérifié.** Un jury technique pardonne une limite déclarée honnêtement, jamais une affirmation fausse. Évitez « inviolable », « sécurité parfaite », « 100 % sûr ».

## 0. Avant de passer devant le jury

1. Repartir d'une pile neuve : `docker compose down -v && docker compose up -d` (attendre 1 à 2 minutes pour Keycloak), puis `docker compose logs bootstrap` (5 comptes créés). Chaque compte démo devra configurer son TOTP à la première connexion : **configurez-les à l'avance** avec une application sur votre téléphone, sinon vous perdrez du temps devant le jury.
2. Deux navigateurs prêts : `agent.demo1` (normal) et `agent.demo2` (navigation privée), clés de récupération créées, une discussion ouverte entre les deux.
3. Un terminal prêt dans le dossier du projet. Chaque révocation de `agent.demo2` est définitive : pour la rejouer, recréer la pile.
4. Tester **hors ligne** (couper le réseau après le premier démarrage) pour confirmer l'absence de service tiers.
5. Vérifier dans le règlement si l'usage d'une IA pour produire le code doit être déclaré. Si oui, le déclarer. Dans tous les cas, **chaque membre doit pouvoir expliquer chaque fichier**.

## 1. Les épreuves possibles et comment les passer

### A. « Le serveur ne lit rien »
1. Envoyer `TESTCLAIR-12345` entre les deux agents, puis un fichier contenant un marqueur.
2. `sh tests/check_no_plaintext.sh TESTCLAIR-12345` : doit afficher « OK ».
3. Montrer le contenu stocké :
   `docker compose exec -T db psql -U synapse -d synapse -c "select ej.json from event_json ej join events e using(event_id) where e.type='m.room.encrypted' limit 1;"`
   On y lit `algorithm`, `ciphertext`, `device_id`, `sender_key` et **aucun texte de message**.
4. Trafic réseau (**à tester avant le passage, commande non encore exécutée**) :
   `sudo tcpdump -i any -nn -A port 443 -c 300 | grep -c TESTCLAIR` doit renvoyer 0 (TLS).

À dire : « Le chiffrement est fait dans le navigateur avant l'envoi. Le serveur ne reçoit que du chiffré. »
À admettre : le serveur voit les métadonnées (section 3).

### B. Révocation en pleine conversation
1. Les deux fenêtres ouvertes sur la discussion.
2. `python3 scripts/admin.py revoke agent.demo2`
3. Montrer : la fenêtre privée affiche « Appareil supprimé », la reconnexion est refusée, `agent.demo1` voit « agent.demo2 a quitté le salon ».

À dire : « Le compte est désactivé, les jetons et appareils supprimés, l'agent sort des salles, et les clients renouvellent les clés du groupe. »
À admettre : ce qu'un appareil a **déjà déchiffré** reste lisible sur cet appareil.

### C. Intrus non enrôlé
- Inscription : `curl -sk -X POST https://localhost/_matrix/client/v3/register -H 'Content-Type: application/json' -d '{"username":"intrus","password":"Intrus-Demo-2026!","auth":{"type":"m.login.dummy"}}'` doit répondre 403 `Registration has been disabled`.
- Connexion d'un compte inexistant : refus dans Element.
- Un agent enrôlé **non invité** ne peut pas rejoindre une salle privée (à montrer en direct).

### D. Démonstration de l'innovation
**Rien d'innovant n'est implémenté.** Ne présentez que ce qui tourne réellement. Si vous gagnez du temps, l'option la plus réaliste est l'expiration automatique des messages (rétention Synapse).

### E. Explication d'une fonction par un membre désigné
Voir sections 2 et 4 : chacun doit maîtriser les trois blocs.

## 2. Ce que chaque membre doit savoir expliquer

### Le chiffrement (Matrix : Olm et Megolm)
- **Olm** : session chiffrée entre deux appareils, utilisée pour échanger des clés. **Megolm** : session de groupe. L'expéditeur crée une clé de session, la distribue à chaque appareil des membres via Olm, puis chiffre ses messages avec.
- Les clés privées sont **générées et stockées dans le navigateur** de l'agent. Le serveur n'en a jamais.
- Les fichiers sont chiffrés côté client avant envoi ; leur clé voyage dans un message chiffré.
- **Clé de récupération** : elle chiffre la sauvegarde des clés sur le serveur. Sans elle, le serveur ne peut rien lire.
- Les primitives (Curve25519, Ed25519, AES-256, HMAC-SHA-256) sont à vérifier dans la spécification Matrix avant de les citer au jury : https://spec.matrix.org
- **Nous n'avons écrit aucune cryptographie.** C'est une exigence du règlement et un choix de conception.

### L'authentification et l'enrôlement
- L'inscription publique est fermée (`enable_registration: false`). Seul un administrateur crée un compte (`admin.py enroll`).
- Les mots de passe sont hachés par Synapse (bcrypt), jamais stockés en clair. Politique : 12 caractères minimum avec chiffre, majuscule, minuscule et symbole.
- Limitation des tentatives : par compte (`rc_login.account`) et par adresse IP (`rc_login.address`, volontairement large à cause du NAT). Vérifié : 5 échecs puis HTTP 429.
- **Deuxième facteur** : Keycloak demande le mot de passe puis un code TOTP ; Synapse n'accepte que cette connexion (OIDC) et son mot de passe local est désactivé, donc le second facteur ne se contourne pas. Preuve à montrer : `curl -s http://127.0.0.1:8008/_matrix/client/v3/login` ne liste pas `m.login.password`. **Ne l'affirmez que si vous avez validé la page de connexion Keycloak sur votre pile.**

### La révocation (`scripts/admin.py`, fonction `cmd_revoke`)
1. Récupère la liste des appareils.
2. Appelle `deactivate` : jetons invalidés, appareils supprimés, retrait des salles.
3. **Attend et vérifie** (boucle de 20 s) que le compte est désactivé, sans appareil ni salle. Pourquoi : Synapse retire l'agent des salles en arrière-plan ; un premier essai concluait « incomplet » à tort.
4. N'affiche « REVOCATION VERIFIEE » que si les trois conditions sont remplies.

### Le déploiement (`docker-compose.yml`)
- `init` génère les secrets une fois (volume `generated`, rien dans le dépôt) et rend `homeserver.yaml`. Il donne aussi les droits sur `/data` à l'UID 991 (utilisateur de Synapse).
- `db` : PostgreSQL ; `synapse` : serveur Matrix ; `element` : client web ; `caddy` : TLS avec autorité interne (aucun Let's Encrypt).
- L'API d'administration (port 8008) n'est accessible que depuis la machine (`127.0.0.1`), et Caddy n'expose que `/_matrix/*`.
- `bootstrap` crée les comptes fictifs de démonstration.

### Les options de `config/init/homeserver.yaml.tpl` à connaître
`federation_domain_whitelist: []` (aucune fédération), `trusted_key_servers: []`, `url_preview_enabled: false` (le serveur ne va chercher aucune URL), `push.include_content: false`, `presence.enabled: false`, `user_ips_max_age: 7d`, `encryption_enabled_by_default_for_room_type: all` (toute salle chiffrée), `require_auth_for_profile_requests: true`.

## 3. Métadonnées que le serveur voit encore

Identités des comptes, appartenance aux salles, horodatage et taille de chaque évènement, type d'évènement, noms et identifiants d'appareils, adresse IP et agent utilisateur des connexions, profils (nom, avatar), accusés de lecture, taille des fichiers.

Réductions appliquées : pas de fédération, pas de présence, pas d'aperçu d'URL, pas de contenu dans les notifications, journaux d'accès coupés, conservation des IP limitée à 7 jours. **Elles réduisent l'exposition sans la supprimer.**

## 4. Questions pièges et réponses honnêtes

| Question | Réponse |
|---|---|
| Avez-vous écrit la cryptographie ? | Non. Matrix (Olm/Megolm) via les bibliothèques officielles d'Element. Nous configurons et durcissons. |
| Pourquoi Matrix plutôt que Signal, MLS ou OMEMO ? | Signal dépend de services tiers (SMS, push, stockage). MLS est une bibliothèque sans serveur ni client. OMEMO a des clients de groupe inégaux. Matrix fournit serveur, client, groupes, fichiers et multi-appareils auto-hébergeables. |
| Où est le deuxième facteur ? | Keycloak impose un code TOTP à la première connexion puis à chaque connexion ; Synapse n'accepte que la connexion OIDC (mot de passe local désactivé). Limite : le TOTP est imposé par une action requise, un administrateur Keycloak pourrait la retirer ; et Keycloak devient un point de dépendance. |
| Que se passe-t-il si un téléphone est volé et déverrouillé ? | La révocation coupe l'accès au serveur. Les messages déjà déchiffrés sur l'appareil restent lisibles. Il faudrait un verrouillage applicatif et un effacement local. |
| Que peut faire un serveur compromis ? | Lire les métadonnées, refuser le service, et tenter d'ajouter un appareil malveillant. La vérification croisée des appareils (cross-signing) protège contre cela mais n'est pas imposée dans notre configuration. |
| La sauvegarde est-elle sûre ? | `backup.sh` sauvegarde la base et les médias : les messages restent chiffrés, mais les métadonnées sont lisibles. Il faut chiffrer la sauvegarde et la stocker hors du serveur. |
| Aucun service tiers ? | Les images Docker sont téléchargées à l'installation. Ensuite, aucune dépendance : pas de push, pas de fédération, TLS interne. |
| Pourquoi les notifications push mobiles sont absentes ? | Elles passent par Google (FCM) ou Apple (APNs), des tiers. |
| Que prouve votre test « serveur ne lit rien » ? | 0 message en clair en base, marqueurs absents de la base et des médias, 2 évènements chiffrés. Ne prouve pas qu'aucune fuite n'existe ailleurs (sauvegardes, journaux). |
| Quel est le niveau d'engagement ? | Étendre et adapter. |

## 5. Entraînement (à faire à plusieurs)

Chaque membre tire une question au hasard parmi les sections 2 et 4 et répond en moins de deux minutes, sans notes. Puis chacun refait la démonstration de révocation seul, de la pile neuve jusqu'à `REVOCATION VERIFIEE`.

Si un membre ne peut pas expliquer un mécanisme, relisez ensemble le fichier correspondant jusqu'à ce que ce soit le cas : c'est l'épreuve éliminatoire.
