# Configuration Synapse durcie — rendue par config/init/init.sh
# ATTENTION : server_name ne peut plus être changé après le premier démarrage.
server_name: "__SERVER_NAME__"
public_baseurl: "__PUBLIC_URL__/"
pid_file: /data/homeserver.pid

listeners:
  - port: 8008
    tls: false
    type: http
    x_forwarded: true
    resources:
      - names: [client]
        compress: false

database:
  name: psycopg2
  args:
    user: synapse
    password: "__POSTGRES_PASSWORD__"
    database: synapse
    host: db
    cp_min: 5
    cp_max: 10

log_config: "/generated/log.config"
media_store_path: /data/media_store
signing_key_path: "/data/__SERVER_NAME__.signing.key"

registration_shared_secret: "__REGISTRATION_SECRET__"
macaroon_secret_key: "__MACAROON_SECRET__"
form_secret: "__FORM_SECRET__"

# --- Souveraineté : aucun service tiers ---
report_stats: false
trusted_key_servers: []
suppress_key_server_warning: true
federation_domain_whitelist: []          # liste vide : aucune fédération
allow_public_rooms_over_federation: false
url_preview_enabled: false               # le serveur ne va chercher aucune URL
push:
  include_content: false                 # jamais de contenu dans les notifications

# --- Identité : seuls les agents enrôlés ---
enable_registration: false
allow_guest_access: false
allow_public_rooms_without_auth: false
require_auth_for_profile_requests: true
password_config:
  enabled: true
  policy:
    enabled: true
    minimum_length: 12
    require_digit: true
    require_lowercase: true
    require_uppercase: true
    require_symbol: true

# --- E2EE par défaut pour toutes les salles ---
encryption_enabled_by_default_for_room_type: all

# --- Réduction des métadonnées ---
presence:
  enabled: false
user_ips_max_age: 7d
user_directory:
  enabled: true
  search_all_users: true                 # annuaire officiel des agents

# --- Limitation des tentatives et des abus ---
# Limite par adresse IP volontairement large : plusieurs agents partagent souvent la même IP de sortie (NAT).
# La protection contre le brute-force repose sur les limites par compte ci-dessous.
rc_login:
  address:
    per_second: 1
    burst_count: 50
  account:
    per_second: 0.1
    burst_count: 5
  failed_attempts:
    per_second: 0.1
    burst_count: 5
rc_message:
  per_second: 5
  burst_count: 20
max_upload_size: 50M
