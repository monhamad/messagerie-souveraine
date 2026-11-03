#!/bin/sh
# Initialisation : génère les secrets une seule fois, rend la configuration de Synapse
# et (mode oidc) le realm Keycloak. Aucun secret n'est stocké dans le dépôt :
# ils vivent dans le volume Docker "generated".
set -eu

G="${GENERATED_DIR:-/generated}"
I="${INIT_DIR:-/init}"
KC_IMPORT="${KC_IMPORT_DIR:-/kc_import}"
DEMO_CSV="${DEMO_CSV:-/demo/comptes-demo.csv}"
SERVER_NAME="${SERVER_NAME:-localhost}"
PUBLIC_URL="${PUBLIC_URL:-https://localhost}"
AUTH_MODE="${AUTH_MODE:-oidc}"

case "$AUTH_MODE" in
  oidc|password) ;;
  *) echo "init: AUTH_MODE invalide ($AUTH_MODE) : attendu oidc ou password"; exit 1 ;;
esac

gen() { tr -dc 'a-f0-9' < /dev/urandom | head -c 48; }

for f in postgres_password registration_secret macaroon_secret form_secret oidc_secret; do
  [ -s "$G/$f" ] || gen > "$G/$f"
done
chmod 644 "$G"/postgres_password "$G"/registration_secret "$G"/macaroon_secret "$G"/form_secret "$G"/oidc_secret

# 1. Bloc d'authentification (oidc : connexion unique avec second facteur ; password : repli sans 2FA)
TPL="$(mktemp)"
sed -e '/__AUTH_BLOCK__/{' -e "r $I/auth-$AUTH_MODE.yaml.part" -e 'd' -e '}' "$I/homeserver.yaml.tpl" > "$TPL"

sed \
  -e "s|__SERVER_NAME__|$SERVER_NAME|g" \
  -e "s|__PUBLIC_URL__|$PUBLIC_URL|g" \
  -e "s|__POSTGRES_PASSWORD__|$(cat "$G/postgres_password")|g" \
  -e "s|__REGISTRATION_SECRET__|$(cat "$G/registration_secret")|g" \
  -e "s|__MACAROON_SECRET__|$(cat "$G/macaroon_secret")|g" \
  -e "s|__FORM_SECRET__|$(cat "$G/form_secret")|g" \
  -e "s|__OIDC_SECRET__|$(cat "$G/oidc_secret")|g" \
  "$TPL" > "$G/homeserver.yaml"
rm -f "$TPL"

cp "$I/log.config" "$G/log.config"
chmod 644 "$G/homeserver.yaml" "$G/log.config"

# 2. Realm Keycloak (mode oidc) : utilisateurs de démonstration issus de demo/comptes-demo.csv
if [ "$AUTH_MODE" = "oidc" ]; then
  [ -f "$DEMO_CSV" ] || { echo "init: $DEMO_CSV introuvable"; exit 1; }
  if grep -v '^#' "$DEMO_CSV" | grep -q '["\\]'; then
    echo "init: guillemet ou antislash interdit dans $DEMO_CSV"; exit 1
  fi
  USERS="$(mktemp)"
  awk -F, '
    /^#/ || NF < 3 || $1 == "user" { next }
    {
      if (n++) printf ",\n"
      printf "    {\"username\":\"%s\",\"enabled\":true,\"firstName\":\"%s\",\"lastName\":\"Demo\",\"email\":\"%s@demo.local\",\"emailVerified\":true,\"credentials\":[{\"type\":\"password\",\"value\":\"%s\",\"temporary\":false}],\"requiredActions\":[\"CONFIGURE_TOTP\"]}", $1, $1, $1, $2
    }
    END { printf "\n" }
  ' "$DEMO_CSV" > "$USERS"

  awk -v f="$USERS" '$0 == "__USERS__" { while ((getline l < f) > 0) print l; next } { print }' \
    "$I/realm.json.tpl" \
    | sed -e "s|__OIDC_SECRET__|$(cat "$G/oidc_secret")|g" -e "s|__PUBLIC_URL__|$PUBLIC_URL|g" \
    > "$KC_IMPORT/souverain-realm.json"
  chmod 644 "$KC_IMPORT/souverain-realm.json"
  rm -f "$USERS"
fi

# 3. Droits sur les volumes de données : Synapse tourne en UID 991, Keycloak en UID 1000.
[ -d /data ] && chown 991:991 /data || true
[ -d /kc_data ] && chown 1000:0 /kc_data || true

echo "init: configuration générée pour $SERVER_NAME (authentification : $AUTH_MODE)"
