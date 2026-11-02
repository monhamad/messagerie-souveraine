#!/bin/sh
# Restauration d'une sauvegarde créée par scripts/backup.sh.
set -eu
IN="${1:?usage: scripts/restore.sh <dossier-de-sauvegarde>}"
docker compose up -d db
docker compose stop synapse caddy >/dev/null 2>&1 || true
docker compose exec -T db pg_restore -U synapse -d synapse --clean --if-exists < "$IN/synapse.pgdump"
docker compose run --rm --no-deps -v "$PWD/$IN:/backup:ro" --entrypoint tar synapse xzf /backup/synapse_data.tgz -C /data
docker compose up -d
echo "Restauration terminée depuis $IN"
