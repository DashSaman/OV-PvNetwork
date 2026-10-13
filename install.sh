#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
REPO="DashSaman/OV-PvNetwork"
REF="${PVNETWORK_REF:-v1.0.42}"
[[ "$REF" =~ ^v1\.0\.[0-9]+$ ]] || { echo '[PVNetwork] immutable release version required' >&2; exit 2; }
[[ "${EUID:-$(id -u)}" -eq 0 ]] || { echo '[PVNetwork] run as root' >&2; exit 2; }
for tool in curl python3; do
  command -v "$tool" >/dev/null || { apt-get update -y; apt-get install -y ca-certificates curl python3; break; }
done
TMP="$(mktemp -d /tmp/pvnetwork-install.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
ASSET="pvnetwork-panel-${REF}.tar.gz"
URL="https://github.com/${REPO}/releases/download/${REF}/${ASSET}"
curl -fL --retry 3 --connect-timeout 10 "$URL" -o "$TMP/$ASSET"
curl -fL --retry 3 --connect-timeout 10 "$URL.sha256" -o "$TMP/checksum"
# Never let an untrusted checksum select a different local file.
HASH="$(awk 'NF==2 {print $1}' "$TMP/checksum")"
[[ "$HASH" =~ ^[a-fA-F0-9]{64}$ && "$(wc -l < "$TMP/checksum")" -eq 1 ]] || { echo '[PVNetwork] malformed release checksum' >&2; exit 3; }
printf '%s  %s\n' "$HASH" "$ASSET" > "$TMP/expected.sha256"
(cd "$TMP" && sha256sum -c --strict expected.sha256) || exit 3
python3 - "$TMP/$ASSET" "$TMP/src" "${REF#v}" <<'PY'
import json, pathlib, sys, tarfile
archive,destination,version=sys.argv[1:]
with tarfile.open(archive,'r:gz') as tar:
    members=tar.getmembers()
    if len(members)>10000 or sum(m.size for m in members)>256*1024**2:raise SystemExit('release exceeds safety limits')
    for m in members:
        path=pathlib.PurePosixPath(m.name)
        if path.is_absolute() or '..' in path.parts or '\\' in m.name or not (m.isfile() or m.isdir()):raise SystemExit('unsafe release archive member')
    files=[m for m in members if m.isfile()]
    names={str(pathlib.PurePosixPath(m.name)) for m in files}
    versions=[m for m in files if pathlib.PurePosixPath(m.name).name=='VERSION' and
              str(pathlib.PurePosixPath(m.name).parent/'manifest.json') in names and
              str(pathlib.PurePosixPath(m.name).parent/'frontend/package.json') in names]
    if len(versions)!=1 or versions[0].size>100:raise SystemExit('ambiguous release version')
    prefix=pathlib.PurePosixPath(versions[0].name).parent
    mapping={str(pathlib.PurePosixPath(m.name).relative_to(prefix)):m for m in files}
    if len(mapping)!=len(files):raise SystemExit('duplicate release archive path')
    if tar.extractfile(mapping['VERSION']).read().decode().strip()!=version:raise SystemExit('wrong release version')
    if 'node-agent/VERSION' in mapping:
        agent=mapping['node-agent/VERSION']
        if agent.size>100 or tar.extractfile(agent).read().decode().strip()!=version:raise SystemExit('inconsistent node agent version')
    for name in ['manifest.json','frontend/package.json']:
        if mapping[name].size>1000000:raise SystemExit('release metadata too large')
        if json.load(tar.extractfile(mapping[name]))['version']!=version:raise SystemExit('inconsistent release metadata')
    for required in ['install-local.sh','main.py']:
        if required not in mapping:raise SystemExit('incomplete release')
    root=pathlib.Path(destination);root.mkdir(mode=0o700)
    # Copy regular files only after validating every member, never archive links.
    for name,m in mapping.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        with tar.extractfile(m) as source,target.open('wb') as dest:dest.write(source.read())
        target.chmod(m.mode & 0o777)
PY
export PVNETWORK_SOURCE_SHA256="$HASH" PVNETWORK_RELEASE_VERSION="${REF#v}"
bash "$TMP/src/install-local.sh" "$@"
