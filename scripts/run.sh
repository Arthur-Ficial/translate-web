#!/usr/bin/env bash
# Run translate over every corpus item using the args in the manifest.
# Output: data/<id>.json (the JSON output) + data/<id>.txt (plain rendering).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/corpus/manifest.json"
SOURCE="$ROOT/corpus/files"
DEST="$ROOT/data"

mkdir -p "$DEST"

if ! command -v translate >/dev/null 2>&1; then
    echo "translate-web: translate binary not found in PATH."
    echo "  brew install Arthur-Ficial/tap/translate"
    exit 1
fi

TRANSLATE="$(command -v translate)"
VERSION=$($TRANSLATE --version 2>/dev/null | head -1 | awk '{print $1}' | sed 's/^v//')
echo "translate-web: running translate $VERSION over corpus..."

count=$(jq '.items | length' "$MANIFEST")

for i in $(seq 0 $((count - 1))); do
    id=$(jq -r ".items[$i].id" "$MANIFEST")
    filename=$(jq -r ".items[$i].filename" "$MANIFEST")
    file="$SOURCE/$filename"

    if [ ! -f "$file" ]; then
        echo "  $id  SKIP (file not fetched)"
        continue
    fi

    args_json=$(jq -c ".items[$i].translate_args" "$MANIFEST")
    mapfile -t args < <(echo "$args_json" | jq -r '.[]')

    json_out="$DEST/$id.json"
    plain_out="$DEST/$id.txt"
    err_out="$DEST/$id.err"

    printf "  %-40s " "$id"

    # Detect-only is special — it prints `lang\tconfidence` to stdout, not
    # JSON. Capture the same way so the renderer treats it as a code block.
    is_detect=$(echo "$args_json" | jq 'index("--detect-only")')
    if [ "$is_detect" != "null" ]; then
        # No --format flag for detect-only
        if "$TRANSLATE" "${args[@]}" < "$file" > "$plain_out" 2> "$err_out"; then
            # Mirror plain into json file as a synthetic record so build.sh has
            # something stable to load.
            line=$(head -1 "$plain_out" | tr -d '\r')
            lang=$(echo "$line" | awk -F'\t' '{print $1}')
            conf=$(echo "$line" | awk -F'\t' '{print $2}')
            printf '{"detect":{"language":"%s","confidence":%s}}\n' "$lang" "$conf" > "$json_out"
            echo "OK"
        else
            echo "ERROR -- see $err_out"
        fi
        continue
    fi

    # Normal translate path: --format json was added in the manifest.
    if "$TRANSLATE" "${args[@]}" < "$file" > "$json_out" 2> "$err_out"; then
        # Plain rendering: re-run with --format plain to get a plain dst
        plain_args=()
        for a in "${args[@]}"; do
            if [ "$a" = "json" ] || [ "$a" = "ndjson" ]; then plain_args+=("plain"); else plain_args+=("$a"); fi
        done
        "$TRANSLATE" "${plain_args[@]}" < "$file" > "$plain_out" 2>> "$err_out" || true
        echo "OK"
    else
        echo "ERROR -- see $err_out"
    fi
done

echo ""
echo "translate-web: results written to $DEST/"
