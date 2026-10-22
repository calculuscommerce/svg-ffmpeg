#!/usr/bin/env bash
# Push the code to the server and restart. Usage: deploy/deploy.sh ec2-user@HOST [path/to/key]
#   - builds the frontend locally, rsyncs source + dist (no node_modules/data/.venv)
#   - copies backend/.env only if the server has none
#   - installs/updates deps on the server and restarts the service
set -euo pipefail
HOST=${1:?host}; KEY=${2:-}
SSH="ssh -o StrictHostKeyChecking=accept-new ${KEY:+-i $KEY}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
( cd "$HERE/frontend" && npm run build >/dev/null )
$SSH $HOST 'sudo mkdir -p /opt/sketchboard && sudo chown $USER /opt/sketchboard'
rsync -az --delete -e "$SSH" \
  --exclude node_modules --exclude .venv --exclude data --exclude out --exclude .git --exclude '.DS_Store' --exclude backend/.env \
  "$HERE/" $HOST:/opt/sketchboard/
$SSH $HOST 'test -f /opt/sketchboard/backend/.env' 2>/dev/null || scp ${KEY:+-i $KEY} "$HERE/backend/.env" $HOST:/opt/sketchboard/backend/.env
$SSH $HOST 'cd /opt/sketchboard && bash deploy/install.sh && sudo systemctl restart sketchboard && sleep 3 && curl -s localhost:8010/api/health'
echo; echo "deployed to $HOST"
