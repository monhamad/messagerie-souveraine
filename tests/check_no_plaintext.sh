#!/bin/sh
# Épreuve « le serveur ne lit rien » : inspecte la base PostgreSQL de Synapse.
# Usage : tests/check_no_plaintext.sh [MARQUEUR]
#   MARQUEUR : texte distinctif que vous avez envoyé dans un message (ex. TESTCLAIR-12345).
# Code de sortie : 0 = aucun clair trouvé ; 1 = clair trouvé ; 2 = test non concluant.
set -eu

MARKER="${1:-}"
psql_q() { docker compose exec -T db psql -U synapse -d synapse -At; }

echo "== Types d'évènements stockés par le serveur"
echo "select type, count(*) from events group by type order by 2 desc;" | psql_q

CLEAR=$(echo "select count(*) from events where type = 'm.room.message';" | psql_q)
ENC=$(echo "select count(*) from events where type = 'm.room.encrypted';" | psql_q)
echo "== m.room.message (clair) : $CLEAR   |   m.room.encrypted : $ENC"

STATUS=0
if [ "$CLEAR" != "0" ]; then
  echo "ECHEC : des messages sont stockés en clair (salle non chiffrée ?)"; STATUS=1
fi
if [ "$ENC" = "0" ]; then
  echo "NON CONCLUANT : aucun message chiffré en base, envoyez d'abord des messages."; [ $STATUS -eq 0 ] && STATUS=2
fi

if [ -n "$MARKER" ]; then
  HITS=$(printf "select count(*) from event_json where position(:'m' in json) > 0;\n" \
    | docker compose exec -T db psql -U synapse -d synapse -At -v m="$MARKER")
  echo "== Occurrences de '$MARKER' dans event_json : $HITS"
  [ "$HITS" != "0" ] && { echo "ECHEC : le marqueur est lisible en base"; STATUS=1; }

  FILES=$(docker compose exec -T synapse sh -c "grep -rlF -- '$MARKER' /data/media_store 2>/dev/null | wc -l")
  echo "== Fichiers du dépôt de médias contenant '$MARKER' : $FILES"
  [ "$FILES" != "0" ] && { echo "ECHEC : le marqueur est lisible dans les médias"; STATUS=1; }
fi

[ $STATUS -eq 0 ] && echo "OK : aucun message en clair côté serveur."
exit $STATUS
