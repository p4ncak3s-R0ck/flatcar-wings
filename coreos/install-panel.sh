#!/usr/bin/env bash
# Fresh Pterodactyl Panel 1.x installation on Fedora CoreOS.
# Runs alongside the native Wings service; does not change its configuration.
set -Eeuo pipefail
umask 077

die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
[[ $EUID == 0 ]] || die 'Run with sudo bash.'
# shellcheck disable=SC1091
source /etc/os-release
[[ ${ID:-} == fedora && ${VARIANT_ID:-} == coreos ]] || die 'Fedora CoreOS is required.'
for tool in docker curl od base64 systemctl ss; do
    command -v "$tool" >/dev/null || die "Missing required command: $tool"
done
exec 3<>/dev/tty || die 'An interactive terminal is required.'
state=/var/opt/coreos-panel
[[ ! -e $state ]] || die "Existing installation state at $state; refusing to replace credentials or data."
systemctl enable --now docker
for name in coreos-panel coreos-panel-db coreos-panel-cache; do
    ! docker container inspect "$name" >/dev/null 2>&1 || die "Container already exists: $name"
done
! docker network inspect coreos-panel-net >/dev/null 2>&1 || die 'Network coreos-panel-net already exists.'
for name in database cache var nginx certs logs; do
    ! docker volume inspect "coreos-panel-$name" >/dev/null 2>&1 || die "Volume already exists: coreos-panel-$name"
done
if ss -H -ltn '( sport = :80 or sport = :443 )' | read -r _; then
    die 'TCP port 80 or 443 is already in use.'
fi

printf '\nPanel URL (https://panel.example.com, or http://LAN-IP): ' >&3
read -r panel_url <&3
panel_url=${panel_url%/}
[[ $panel_url =~ ^https?://[A-Za-z0-9.-]+$ ]] || die 'Use http://IP or https://hostname with no path or custom port.'
le_email=
if [[ $panel_url == https://* ]]; then
    printf 'DNS must point to this server and inbound TCP 80/443 must reach it.\n' >&3
    printf "Certificate email (Let's Encrypt): " >&3
    read -r le_email <&3
    [[ $le_email =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die 'Enter a valid certificate email.'
    printf "Certificate issuance accepts Let's Encrypt terms: https://letsencrypt.org/repository/\nContinue? [y/N]: " >&3
    read -r answer <&3
    [[ $answer == y || $answer == Y ]] || die 'Cancelled before installation.'
else
    printf 'HTTP sends login details without encryption. Use it only on a trusted LAN.\n' >&3
fi

# Pin the stable Panel release; use the maintained MariaDB 11.4 and Redis 7.4 series.
panel_image=ghcr.io/pterodactyl/panel:v1.15.1@sha256:e27a06cfcd078691ddf9805ae0dee2ee529b35ce18e427ef970de4d503602f2c
docker pull "$panel_image"
docker pull mariadb:11.4
docker pull redis:7.4-alpine
install -d -m 700 "$state"
trap 'printf "Setup stopped. Data is retained at %s and in coreos-panel-* Docker volumes.\nInspect: sudo docker logs coreos-panel\n" "$state" >&2' ERR
random_hex() { od -An -N32 -tx1 /dev/urandom | tr -d ' \n'; }
db_password=$(random_hex)
root_password=$(random_hex)
app_key="base64:$(head -c 32 /dev/urandom | base64 -w0)"
salt=$(random_hex)
cat >"$state/database.env" <<EOF
MARIADB_DATABASE=panel
MARIADB_USER=pterodactyl
MARIADB_PASSWORD=$db_password
MARIADB_ROOT_PASSWORD=$root_password
EOF
cat >"$state/panel.env" <<EOF
APP_ENV=production
APP_DEBUG=false
APP_URL=$panel_url
APP_TIMEZONE=America/New_York
APP_SERVICE_AUTHOR=noreply@localhost
APP_ENVIRONMENT_ONLY=true
APP_KEY=$app_key
HASHIDS_SALT=$salt
HASHIDS_LENGTH=8
DB_CONNECTION=mysql
DB_HOST=database
DB_PORT=3306
DB_DATABASE=panel
DB_USERNAME=pterodactyl
DB_PASSWORD=$db_password
REDIS_HOST=cache
REDIS_PORT=6379
CACHE_DRIVER=redis
SESSION_DRIVER=redis
QUEUE_CONNECTION=redis
QUEUE_DRIVER=redis
MAIL_MAILER=log
MAIL_DRIVER=log
MAIL_FROM_ADDRESS=noreply@localhost
LE_EMAIL=$le_email
EOF
docker network create coreos-panel-net >/dev/null
for name in database cache var nginx certs logs; do
    docker volume create "coreos-panel-$name" >/dev/null
done
# Preseed encryption keys so the upstream entrypoint never prints new keys to logs.
docker run --rm --network none --env-file "$state/panel.env" \
    -v coreos-panel-var:/app/var --entrypoint /bin/ash "$panel_image" -ec \
    'printf "APP_KEY=%s\nHASHIDS_SALT=%s\n" "$APP_KEY" "$HASHIDS_SALT" > /app/var/.env; chown nginx:nginx /app/var/.env; chmod 640 /app/var/.env'
docker run -d --name coreos-panel-db --restart unless-stopped \
    --network coreos-panel-net --network-alias database \
    --env-file "$state/database.env" -v coreos-panel-database:/var/lib/mysql \
    mariadb:11.4 >/dev/null
printf 'Waiting for MariaDB initialization...\n'
ready=false
for ((i=0; i<120; i++)); do
    if docker exec coreos-panel-db healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then
        ready=true; break
    fi
    sleep 2
done
[[ $ready == true ]] || die 'Database did not become ready. Check: sudo docker logs coreos-panel-db'
docker run -d --name coreos-panel-cache --restart unless-stopped \
    --network coreos-panel-net --network-alias cache \
    -v coreos-panel-cache:/data redis:7.4-alpine redis-server --appendonly yes >/dev/null
docker run -d --name coreos-panel --restart unless-stopped \
    --network coreos-panel-net --env-file "$state/panel.env" \
    -p 80:80 -p 443:443 \
    -v coreos-panel-var:/app/var \
    -v coreos-panel-nginx:/etc/nginx/http.d \
    -v coreos-panel-certs:/etc/letsencrypt \
    -v coreos-panel-logs:/app/storage/logs "$panel_image" >/dev/null
printf 'Waiting for Panel setup, database migrations, and web server...\n'
ready=false
for ((i=0; i<180; i++)); do
    if curl --noproxy '*' --fail --silent --max-time 3 http://127.0.0.1/ -o /dev/null; then
        ready=true; break
    fi
    sleep 2
done
[[ $ready == true ]] || die 'Panel did not become ready. Check: sudo docker logs coreos-panel'
printf '\nCreate your Panel administrator account:\n' >&3
docker exec -it coreos-panel php artisan p:user:make --admin=1 <&3 >&3 2>&3
printf '\nPanel ready: %s\n' "$panel_url"
printf 'SMTP is not configured; password-reset mail currently goes to Panel logs.\n'
printf 'Back up %s and all coreos-panel-* Docker volumes, including the database and app keys.\n' "$state"
printf 'Next: create a Location and Node in the Panel, save its node configuration to /etc/pterodactyl/config.yml, then run sudo systemctl restart wings.\n'
