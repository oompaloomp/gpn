#!/bin/sh
export PATH=/opt/bin:/opt/sbin:/bin:/sbin:/usr/bin:/usr/sbin:$PATH
cd /opt/gpn || exit 1

git config user.name "Keenetic Bot"
git config user.email "bot@keenetic.local"

echo "=== Stash local changes ==="
git stash push -m "keenetic-auto-stash" 2>/dev/null || true

echo "=== Pull ==="
git pull --rebase origin main
if [ $? -ne 0 ]; then
    echo "rebase failed, trying normal pull"
    git pull origin main || exit 1
fi

git stash pop 2>/dev/null || true

echo "=== Parser ==="
/opt/bin/python3 -m src.gpn_parser --export
if [ $? -ne 0 ]; then
    echo "Parser failed"
    exit 1
fi

echo "=== Copy to docs ==="
mkdir -p docs
cp -f data/stations.json docs/stations.json

echo "=== Commit ==="
git add data/stations.json docs/stations.json

if git diff --cached --quiet; then
    echo "No data changes"
    exit 0
fi

git commit -m "Auto update $(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "=== Push ==="
git push origin main
if [ $? -ne 0 ]; then
    echo "Push rejected, pull --rebase and retry"
    git pull --rebase origin main
    git push origin main || exit 1
fi

echo "OK: pushed to GitHub"
