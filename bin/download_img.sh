#!/bin/bash
# Download Docker image from Wave registry using curl, create docker-archive tar.
# Usage: download_img.sh <name> <registry> <repo> <tag>
set -euo pipefail

NAME=$1; REGISTRY=$2; REPO=$3; TAG=$4
OUTFILE="${NAME}.tar"

echo "=== Downloading $NAME ($REGISTRY/$REPO:$TAG) ==="

# Get token
TOKEN=$(curl -s --max-time 30 \
  "https://cerbero.seqera.io/auth/token?service=$REGISTRY&scope=repository:$REPO:pull" \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# Get manifest
MANIFEST=$(curl -s --max-time 30 -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/vnd.oci.image.manifest.v1+json" \
  "https://${REGISTRY}/v2/${REPO}/manifests/${TAG}")
echo "$MANIFEST" > /dev/null

# Parse config + layers
CONFIG=$(echo "$MANIFEST" | python -c "import sys,json; m=json.load(sys.stdin); print(m['config']['digest'])")
echo "Config: $CONFIG"
echo "Layers:"

# Download config
CONFIG_FILE=$(basename "$CONFIG" | sed 's/sha256://').json
curl -s --max-time 60 -H "Authorization: Bearer $TOKEN" \
  "https://${REGISTRY}/v2/${REPO}/blobs/${CONFIG}" -o "$CONFIG_FILE"
echo "  Config: $CONFIG_FILE ($(wc -c < $CONFIG_FILE) bytes)"

# Download layers
LAYER_NAMES=()
LAYER_INDEX=0
echo "$MANIFEST" | python -c "
import sys, json
m = json.load(sys.stdin)
for i, l in enumerate(m['layers']):
    print(f'{l[\"digest\"]} {l[\"size\"]} {i}')
" | while read digest size idx; do
  if [ $idx -eq 0 ]; then
    LNAME="layer.tar"
  else
    LNAME="layer_${idx}.tar"
  fi
  echo "  Layer $idx: ${digest:0:30} ($((size/1024/1024)) MB) -> $LNAME"
  curl -s --max-time 600 -H "Authorization: Bearer $TOKEN" \
    "https://${REGISTRY}/v2/${REPO}/blobs/${digest}" -o "$LNAME"
  echo "    done ($(wc -c < $LNAME) bytes)"
done

# Create docker-archive tar
echo "Creating $OUTFILE..."
# First, collect all layer names
python -c "
import json, os
m = json.load(open('chopper_manifest.json'))  # fallback
" 2>/dev/null || true

# Build manifest.json
LAYER_LIST=$(python -c "
import json
m = json.load(open('chopper_manifest.json'))
config = m['config']['digest'].replace('sha256:', '') + '.json'
layers = []
for i, l in enumerate(m['layers']):
    layers.append('layer.tar' if i == 0 else f'layer_{i}.tar')
manifest = [{'Config': config, 'RepoTags': [f'$REGISTRY/$REPO:$TAG'], 'Layers': layers}]
with open('manifest.json', 'w') as f:
    json.dump(manifest, f)
")

# Tar everything
tar cf "$OUTFILE" manifest.json "$CONFIG_FILE" layer.tar layer_*.tar 2>/dev/null || true
echo "Done: $OUTFILE ($(stat -c%s "$OUTFILE" 2>/dev/null || echo "?"))"