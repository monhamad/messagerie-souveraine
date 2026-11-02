#!/bin/sh
# Initialisation : génère les secrets une seule fois et rend la configuration de Synapse.
# Aucun secret n'est stocké dans le dépôt : ils vivent dans le volume Docker "generated".
set -eu

G="${GENERATED_DIR:-/generated}"
I="${INIT_DIR:-/init}"
SERVER_NAME="${SERVER_NAME:-localhost}"
PUBLIC_URL="${PUBLIC_URL:-https://localhost}"

gen() { tr -dc 'a-f0-9' < /dev/urandom | head -c 48; }

for f in postgres_password registration_secret macaroon_secret form_secret; do
  [ -s "$G/$f" ] || gen > "$G/$f"
done
chmod 644 "$G"/postgres_password "$G"/registration_secret "$G"/macaroon_secret "$G"/form_secret

sed \
  -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
  -e "s|__PUBLIC_URL__|$PUBLIC_URL|g" \
  -e "s|__POSTGRES_PASSWORD__|$(cat "$G/postgres_password")|g" \
  -e "s|__REGISTRATION_SECRET__|$(cat "$G/registration_secret")|g" \
  -e "s|__MACAROON_SECRET__|$(cat "$G/macaroon_secret")|g" \
  -e "s|__FORM_SECRET__|$(cat "$G/form_secret")|g" \
  "$I/homeserver.yaml.tpl" > "$G/homeserver.yaml"

cp "$I/log.config" "$G/log.config"
chmod 644 "$G/homeserver.yaml" "$G/log.config"
# Le volume de données doit appartenir à l'utilisateur de Synapse (UID 991).
[ -d /data ] && chown 991:991 /data || true
echo "init: configuration générée pour $SERVER_NAME"
