#!/usr/bin/env bash
# Fix "not safe" on arestoteles.de (apex): expand the TLS cert to cover the apex
# and give nginx a 443 vhost for it.
#
# Root cause: the cert was issued for www.arestoteles.de only (the apex did not
# resolve on 2026-06-14). Modern browsers try https://arestoteles.de FIRST, hit
# a 443 fallback serving the ares-empire.de cert -> name mismatch -> warning.
# The HTTP->www redirect never fired because the browser went straight to HTTPS.
#
# Now that arestoteles.de (apex) resolves to this host, this:
#   1. expands the existing `www.arestoteles.de` lineage to also cover the apex,
#   2. adds a 443 server for the apex that 301s to https://www.arestoteles.de
#      (preserving www as the canonical host) using the combined cert.
#
# Validates nginx before reloading, so a mistake won't take down the other sites
# on the shared gateway (insureares, aresium, ares-empire).
#
#   sudo bash deploy/enable-tls-arestoteles-apex.sh
set -euo pipefail

WWW=www.arestoteles.de
APEX=arestoteles.de
EMAIL=you@example.com
PORT=5180
CONF=/root/insureai/InsureAI/backend/nginx/conf.d/arestoteles.conf
CERTBOT_CONF=/root/insureai/InsureAI/backend/certbot/conf
CERTBOT_WWW=/root/insureai/InsureAI/backend/certbot/www

echo "==> Checking both names resolve to this host..."
for d in "$WWW" "$APEX"; do
  ip=$(getent hosts "$d" | awk '{print $1}' | head -1 || true)
  echo "    $d -> ${ip:-<unresolved>}"
  [ -z "$ip" ] && { echo "!! $d does not resolve yet. Wait for DNS, then re-run." >&2; exit 1; }
done

echo "==> Expanding cert to cover the apex (lineage name stays www.arestoteles.de)..."
# --expand matches the existing lineage by its first domain (www.arestoteles.de)
# and adds the apex as a SAN in place, so the live/ path is unchanged.
docker run --rm \
  -v "$CERTBOT_CONF":/etc/letsencrypt \
  -v "$CERTBOT_WWW":/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$WWW" -d "$APEX" --expand \
  --email "$EMAIL" --agree-tos --no-eff-email --non-interactive

echo "==> Writing vhost (www serves the site; apex 301s to www over HTTPS)..."
cat > "$CONF" <<NGINX
# ============================================================
# Arestoteles — AI-run semiconductor portfolio portal (arestoteles.de)
# Additive vhost on the shared insureai_nginx gateway. Coexists with
# default.conf (insureares), aresium.conf, ares-empire.conf — all untouched.
# Proxies to the arestoteles \`web\` container on the bridge gateway 172.18.0.1:$PORT.
#
# TLS: the www.arestoteles.de lineage covers BOTH $WWW and $APEX (expanded
# once the apex resolved). www is the canonical host; the apex 301s to it over
# both HTTP and HTTPS, so browsers that try https://$APEX first get a valid cert.
# ============================================================

server {
    listen 80;
    listen [::]:80;
    server_name $APEX $WWW;

    # Let's Encrypt HTTP-01 challenge (certbot drops files here)
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$WWW\$request_uri;
    }
}

# Apex over HTTPS: valid cert (it is now a SAN) + redirect to canonical www.
server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $APEX;

    ssl_certificate     /etc/letsencrypt/live/$WWW/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$WWW/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:SSL_arestoteles_apex:5m;
    ssl_session_tickets off;

    location / {
        return 301 https://$WWW\$request_uri;
    }
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;
    http2 on;
    server_name $WWW;

    ssl_certificate     /etc/letsencrypt/live/$WWW/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$WWW/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL_arestoteles:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    gzip on;
    gzip_types text/plain text/css application/javascript application/json image/svg+xml;
    gzip_min_length 1024;

    # live watchlist feed — revalidate often (regenerated server-side on a timer)
    location = /live.json {
        proxy_pass http://172.18.0.1:$PORT;
        proxy_set_header Host              \$host;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        add_header Cache-Control "no-cache" always;
    }

    location / {
        proxy_pass http://172.18.0.1:$PORT;
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_connect_timeout 10s;
        proxy_read_timeout    30s;
        proxy_send_timeout    30s;
    }
}
NGINX

echo "==> Validating + reloading nginx..."
docker exec insureai_nginx nginx -t
docker exec insureai_nginx nginx -s reload
echo "==> Done. https://$APEX now serves a valid cert and redirects to https://$WWW."
