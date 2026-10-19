#!/usr/bin/env bash
# Deploy the judges' demo from a local clone: upload the tree of one commit (git archive: no GitHub access on the server, no
# working-tree changes), write the server's .env once (a generated password; only its bcrypt hash is stored on the server),
# and build and start the three containers.
#
# usage: infra/judges-demo/deploy.sh <user@ip> <ssh key> [<commit>=HEAD]
# The demo hostname is <ip with dashes>.sslip.io, which resolves to the IP, so Caddy can get a certificate for it.
# The password is printed once, and kept in infra/judges-demo/.credentials (gitignored) on this machine.
set -euo pipefail
TARGET=$1; KEY=$2; REF=${3:-HEAD}
IP=${TARGET#*@}
HOST="${IP//./-}.sslip.io"
SSH=(ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "$TARGET")
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(git -C "$HERE" rev-parse --show-toplevel)
CRED="$HERE/.credentials"

echo "deploying $(git -C "$ROOT" rev-parse --short "$REF") to https://$HOST"
git -C "$ROOT" archive --format=tar.gz "$REF" | "${SSH[@]}" 'rm -rf ~/flow.new && mkdir -p ~/flow.new && tar -xzf - -C ~/flow.new && cat > /dev/null && rm -rf ~/flow && mv ~/flow.new ~/flow'  # cat drains the gzip trailer tar leaves unread (else SIGPIPE)

if [ ! -f "$CRED" ]; then
  PASS=$(python3 -c "import secrets; a='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'; print(''.join(secrets.choice(a) for _ in range(20)))" 2>/dev/null || python -c "import secrets; a='ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'; print(''.join(secrets.choice(a) for _ in range(20)))")
  printf 'url=https://%s\nuser=judges\npassword=%s\n' "$HOST" "$PASS" > "$CRED"; chmod 600 "$CRED"
fi
PASS=$(sed -n 's/^password=//p' "$CRED")
HASH=$("${SSH[@]}" "sudo docker run --rm caddy:2.8.4 caddy hash-password --plaintext '$PASS'")
"${SSH[@]}" "umask 077 && printf \"DEMO_HOST=%s\nDEMO_USER=judges\nDEMO_PASS_HASH='%s'\n\" '$HOST' '$HASH' > ~/flow/infra/judges-demo/.env"
"${SSH[@]}" 'cd ~/flow/infra/judges-demo && { sudo docker compose up -d --build > ~/compose-up.log 2>&1; rc=$?; tail -15 ~/compose-up.log; sudo docker compose ps; exit $rc; }'
echo
echo "URL:      https://$HOST"
echo "user:     judges"
echo "password: (in $CRED)"
