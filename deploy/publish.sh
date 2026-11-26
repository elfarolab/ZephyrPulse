#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${R2_ACCOUNT_ID:?Set R2_ACCOUNT_ID}"
: "${R2_BUCKET:?Set R2_BUCKET}"
: "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID}"
: "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY}"
export AWS_DEFAULT_REGION=auto AWS_PAGER=""
endpoint="https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
release="$(date -u +%Y%m%dT%H%M%SZ)-$(python3 -c 'import uuid; print(uuid.uuid4().hex[:12])')"
[[ -f site/index.html ]]
# Publish immutable release first; pointer is changed only after every upload succeeds.
printf "Uploading website release %s to R2\n" "$release"
aws --endpoint-url "$endpoint" s3 sync site/ "s3://${R2_BUCKET}/releases/${release}/" --no-progress --only-show-errors
pointer=$(mktemp)
trap 'rm -f "$pointer"' EXIT
printf '{"release":"%s"}\n' "$release" > "$pointer"
printf "Upload complete; activating release %s\n" "$release"
aws --endpoint-url "$endpoint" s3 cp "$pointer" "s3://${R2_BUCKET}/current.json" --content-type application/json --cache-control no-store --only-show-errors
printf 'Published %s\n' "$release"
