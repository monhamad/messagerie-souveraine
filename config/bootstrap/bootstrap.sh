#!/bin/sh
# Crée les comptes de démonstration FICTIFS listés dans demo/comptes-demo.csv.
# Idempotent : un compte déjà existant est simplement ignoré.
set -u

CSV=/demo/comptes-demo.csv
[ -f "$CSV" ] || { echo "bootstrap: $CSV introuvable"; exit 1; }

while IFS=, read -r user pass role; do
  case "$user" in ''|'#'*|user) continue ;; esac
  flag="--no-admin"
  [ "$role" = "admin" ] && flag="--admin"
  if register_new_matrix_user -c /generated/homeserver.yaml -u "$user" -p "$pass" "$flag" http://synapse:8008 >/dev/null 2>&1; then
    echo "bootstrap: compte créé : $user ($role)"
  else
    echo "bootstrap: compte ignoré (existe déjà ?) : $user"
  fi
done < "$CSV"
exit 0
