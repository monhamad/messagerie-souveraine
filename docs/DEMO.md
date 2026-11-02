# Scénario de la vidéo (3 minutes maximum)

Préparer avant l'enregistrement : pile démarrée, deux navigateurs (ou profils) connectés en `agent.demo1` et `agent.demo2`, un terminal prêt avec `admin.demo`.

| Temps | Action | À dire |
|---|---|---|
| 0:00-0:20 | Montrer `docker compose up -d` (ou la pile déjà démarrée) | « Une commande, aucun service tiers. » |
| 0:20-1:00 | Créer un groupe, envoyer un message et un fichier entre les deux agents | « Chiffrement de bout en bout avec Matrix, aucune crypto développée par l'équipe. » |
| 1:00-1:30 | `tests/check_no_plaintext.sh MARQUEUR` | « Le serveur ne stocke que du chiffré. » |
| 1:30-2:15 | `scripts/admin.py revoke agent.demo2` pendant la conversation ; montrer que l'agent perd l'accès | « Révocation immédiate sur tous les appareils. » |
| 2:15-2:50 | Fonctionnalité innovante principale | À définir par l'équipe (voir ci-dessous) |
| 2:50-3:00 | Rappeler les limites | « La révocation n'efface pas ce qui est déjà déchiffré. » |

## Innovation : à choisir par l'équipe

Rien d'innovant n'est encore implémenté. Option réaliste à faible coût : expiration automatique des messages (politique de rétention de Synapse) avec un script de classification de salle. Ne présentez que ce qui fonctionne réellement ; l'épreuve « Innovation » est une démonstration en direct.
