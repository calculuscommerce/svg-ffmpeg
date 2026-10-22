#!/usr/bin/env bash
# Build the frontend and publish it to S3 + CloudFront. Usage: deploy/deploy-frontend.sh <bucket> <distribution-id>
set -euo pipefail
B=${1:?bucket}; D=${2:?distribution id}
HERE=$(cd "$(dirname "$0")/.." && pwd)
( cd "$HERE/frontend" && npm run build >/dev/null )
aws s3 sync "$HERE/frontend/dist" "s3://$B" --delete --only-show-errors
aws cloudfront create-invalidation --distribution-id "$D" --paths "/index.html" "/" --query Invalidation.Id --output text
echo "frontend published to $B"
