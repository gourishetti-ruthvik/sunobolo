#!/usr/bin/env bash
# Is the live site running the commit I have locally?
#
# Render's auto-deploy can be enabled and still never fire (it needs a GitHub
# webhook, which an API-created service does not get). That failure is silent,
# so check rather than assume.
set -u
URL="${1:-https://sunobolo.onrender.com}"

local_sha=$(git rev-parse --short=7 HEAD)
live_sha=$(curl -fsS -m 30 "$URL/healthz" | sed -n 's/.*"commit":"\([^"]*\)".*/\1/p')

echo "local : $local_sha"
echo "live  : ${live_sha:-unreachable}"

if [ -z "$live_sha" ]; then
  echo "FAIL  : could not read $URL/healthz"; exit 1
elif [ "$local_sha" = "$live_sha" ]; then
  echo "OK    : the live site is running your latest commit"
else
  echo "STALE : the live site is behind. Deploy, then run this again."; exit 1
fi
