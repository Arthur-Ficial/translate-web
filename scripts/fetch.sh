#!/usr/bin/env bash
# Materialize the corpus. Each item's `text` field in manifest.json is
# already public-domain content (UDHR articles, 19th-century literature,
# composed-for-this-site CC0). We just write it to disk so run.sh can pipe
# real files into the translate binary -- exactly how a user would use it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/corpus/manifest.json"
DEST="$ROOT/corpus/files"

mkdir -p "$DEST"

count=$(jq '.items | length' "$MANIFEST")
echo "translate-web: materializing $count corpus items..."

for i in $(seq 0 $((count - 1))); do
    id=$(jq -r ".items[$i].id" "$MANIFEST")
    filename=$(jq -r ".items[$i].filename" "$MANIFEST")
    target="$DEST/$filename"

    # Always rewrite (cheap, ensures the file matches the manifest exactly).
    jq -r ".items[$i].text" "$MANIFEST" > "$target"
    bytes=$(wc -c < "$target" | tr -d ' ')
    printf "  %-40s %s bytes\n" "$id" "$bytes"
done

echo ""
echo "translate-web: corpus in $DEST"
ls -lh "$DEST" | tail -n +2
