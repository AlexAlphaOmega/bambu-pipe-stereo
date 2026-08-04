#!/usr/bin/env python3
"""Download a Docker image from an OCI registry and save as docker-archive tar.

Usage:
    python download_image.py <image_name> <registry> <repo> <tag> [output.tar]

Example:
    python download_image.py chopper community.wave.seqera.io library/chopper_cutadapt_flexiplex_pigz 077c3bc67452482c
"""
import json, os, sys, tarfile, io, hashlib, requests
from pathlib import Path

def get_token(registry, repo):
    """Get OCI bearer token for anonymous pull."""
    session = requests.Session()
    session.trust_env = False
    r = session.get(f"https://{registry}/v2/", timeout=30)
    if r.status_code == 401:
        auth = r.headers.get("Www-Authenticate", "")
        import re
        realm = re.search(r'realm="([^"]+)"', auth)
        svc = re.search(r'service="([^"]+)"', auth)
        scp = re.search(r'scope="([^"]+)"', auth)
        realm_url = realm.group(1) if realm else ""
        svc_name = svc.group(1) if svc else registry
        scp_name = scp.group(1) if scp else f"repository:{repo}:pull"
        if not realm_url:
            return None
        tr = session.get(f"{realm_url}?service={svc_name}&scope={scp_name}", timeout=30)
        if tr.ok:
            return tr.json()["token"]
    return None

def download_blob(registry, repo, digest, token):
    """Download a blob (layer or config)."""
    url = f"https://{registry}/v2/{repo}/blobs/{digest}"
    session = requests.Session()
    session.trust_env = False
    r = session.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=300)
    r.raise_for_status()
    return r.content

def download_image(name, registry, repo, tag, outfile):
    """Download image + create docker-archive tar."""
    token = get_token(registry, repo)
    if not token:
        print("Failed to get auth token")
        return False

    print(f"Downloading manifest for {name} ({registry}/{repo}:{tag})...")
    session = requests.Session()
    session.trust_env = False
    r = session.get(
        f"https://{registry}/v2/{repo}/manifests/{tag}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.oci.image.manifest.v1+json"
        },
        timeout=30
    )
    r.raise_for_status()
    manifest = r.json()

    config_digest = manifest["config"]["digest"]
    layers = manifest["layers"]

    print(f"Config: {config_digest[:30]}")
    print(f"Layers: {len(layers)}")
    total_bytes = sum(l["size"] for l in layers)
    print(f"Total size: {total_bytes / 1024 / 1024:.1f} MB")

    # Download config
    print("Downloading config...")
    config_data = download_blob(registry, repo, config_digest, token)
    config_sha = config_digest.replace("sha256:", "")
    config_filename = f"{config_sha}.json"

    # Download layers
    layer_files = []
    for i, layer in enumerate(layers):
        digest = layer["digest"]
        size = layer["size"]
        print(f"  Layer {i+1}/{len(layers)}: {digest[:30]} ({size / 1024 / 1024:.1f} MB)...")
        data = download_blob(registry, repo, digest, token)
        layer_filename = f"layer_{i}.tar"
        if i == 0:
            # First layer is the base, use it as layer.tar
            layer_filename = "layer.tar"
        layer_files.append((layer_filename, data, digest))

    # Create docker-archive tar
    print(f"Creating {outfile}...")
    with tarfile.open(outfile, "w") as tar:
        # Add manifest.json
        repo_name = f"{registry}/{repo}:{tag}"
        manifest_entry = [{
            "Config": config_filename,
            "RepoTags": [repo_name],
            "Layers": [f[0] for f in layer_files]
        }]
        tarinfo = tarfile.TarInfo(name="manifest.json")
        manifest_bytes = json.dumps(manifest_entry).encode()
        tarinfo.size = len(manifest_bytes)
        tar.addfile(tarinfo, io.BytesIO(manifest_bytes))

        # Add config
        tarinfo = tarfile.TarInfo(name=config_filename)
        tarinfo.size = len(config_data)
        tar.addfile(tarinfo, io.BytesIO(config_data))

        # Add layers
        for lf_name, lf_data, lf_digest in layer_files:
            tarinfo = tarfile.TarInfo(name=lf_name)
            tarinfo.size = len(lf_data)
            tar.addfile(tarinfo, io.BytesIO(lf_data))

    print(f"Done: {outfile} ({os.path.getsize(outfile) / 1024 / 1024:.1f} MB)")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python download_image.py <name> <registry> <repo> <tag> [out.tar]")
        sys.exit(1)
    name = sys.argv[1]
    registry = sys.argv[2]
    repo = sys.argv[3]
    tag = sys.argv[4]
    outfile = sys.argv[5] if len(sys.argv) > 5 else f"{name}.tar"
    download_image(name, registry, repo, tag, outfile)