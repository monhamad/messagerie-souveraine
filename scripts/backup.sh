#!/bin/sh
# Sauvegarde : base PostgreSQL + dépôt de médias et clé de signature de Synapse.
# ATTENTION : la sauvegarde contient des métadonnées (comptes, salles) : la chiffrer et la stocker hors du serveur.
set -eu
OUT="${1:-backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUT"
docker compose exec -T db pg_dump -U synapse -Fc synapse > "$OUT/synapse.pgdump"
docker compose run --rm --no-deps -v "$PWD/$OUT:/backup" --entrypoint tar synapse czf /backup/synapse_data.tgz -C /data .
echo "Sauvegarde écrite dans $OUT"
