#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="$ROOT/public"
rm -rf "$OUT"
mkdir -p "$OUT/assets" "$OUT/security"
cp "$ROOT/index.html" "$OUT/index.html"
cp "$ROOT/security/index.html" "$OUT/security/index.html"
cp "$ROOT/robots.txt" "$OUT/robots.txt"
cp "$ROOT/sitemap.xml" "$OUT/sitemap.xml"
cp "$ROOT/assets/steward-rig-v1.evidence.json" "$OUT/assets/steward-rig-v1.evidence.json"
cat "$ROOT"/chunks/glb.part*.b64 | base64 -d > "$OUT/assets/steward-rig-v1.glb"
cat "$ROOT"/chunks/zip.part*.b64 | base64 -d > "$OUT/assets/steward-rig-v1-verified-exports.zip"
printf '%s  %s\n' '187819a9086b12366f33f5290db98f7921b55e0674bf4aaee000e76241cb605f' "$OUT/assets/steward-rig-v1.glb" | sha256sum -c -
printf '%s  %s\n' 'd10fc1d7b174630241dbde64a8cedba380e36dfaecc31ddb3bfe75d28b9b1024' "$OUT/assets/steward-rig-v1-verified-exports.zip" | sha256sum -c -
test "$(stat -c %s "$OUT/assets/steward-rig-v1.glb")" = "609908"
test "$(stat -c %s "$OUT/assets/steward-rig-v1-verified-exports.zip")" = "639339"
echo "STEWARD_PUBLIC_SITE_BUILD=PASS"
