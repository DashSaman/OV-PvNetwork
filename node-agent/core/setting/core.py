import re
import os
from pathlib import Path

from core.logger import logger
from core.schema.all_schemas import SetSettingsModel

SERVER_PATH=Path('/etc/openvpn/server/server.conf')
TEMPLATE_PATHS=[Path('/etc/openvpn/server/client-template.txt'),Path('/etc/openvpn/server/client-common.txt')]


def atomic_write(path,value):
    info=path.stat();temporary=path.with_name('.'+path.name+'.pvnetwork-new')
    with temporary.open('w') as handle:
        os.chmod(temporary,info.st_mode&0o777);os.chown(temporary,info.st_uid,info.st_gid)
        handle.write(value);handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)


def change_config(request: SetSettingsModel) -> bool:
    try:
        paths=[SERVER_PATH,*[p for p in TEMPLATE_PATHS if p.is_file()]]
        if len(paths)<2 or any(p.is_symlink() for p in paths):return False
        originals={p:p.read_text() for p in paths}
        configuration=originals[SERVER_PATH]
        match=re.search(r'^proto\s+(\S+)',configuration,re.MULTILINE)
        if not match or not re.search(r'^port\s+\d+',configuration,re.MULTILINE):return False
        configured_protocol=match[1].replace('4','').replace('6','').replace('-server','')
        changed=re.sub(r'^port\s+\d+',f'port {request.ovpn_port}',configuration,flags=re.MULTILINE)
        if configured_protocol!=request.protocol:
            protocol='tcp-server' if request.protocol=='tcp' else 'udp'
            changed=re.sub(r'^proto\s+\S+',f'proto {protocol}',changed,flags=re.MULTILINE)
        updates={SERVER_PATH:changed}
        for path in paths[1:]:
            template=originals[path]
            template=re.sub(r'^remote\s+(\S+)\s+\d+',lambda m:'remote '+(request.tunnel_address or m[1])+' '+str(request.ovpn_port),template,flags=re.MULTILINE)
            protocol_match=re.search(r'^proto\s+(\S+)',template,re.MULTILINE)
            if protocol_match and protocol_match[1].replace('4','').replace('6','').replace('-client','')!=request.protocol:
                template=re.sub(r'^proto\s+\S+','proto '+('tcp-client' if request.protocol=='tcp' else 'udp'),template,flags=re.MULTILINE)
            updates[path]=template
        changed_files=[p for p in paths if updates[p]!=originals[p]]
        if not changed_files:return True
        try:
            for path in changed_files:atomic_write(path,updates[path])
            # Updating a profile endpoint alone does not require VPN downtime.
            if SERVER_PATH in changed_files:restart_openvpn()
        except Exception:
            for path in changed_files:atomic_write(path,originals[path])
            if SERVER_PATH in changed_files:restart_openvpn()
            raise
        logger.info('Explicit node configuration change applied')
        return True
    except Exception as e:
        logger.error('OpenVPN setting change failed')
        return False


def restart_openvpn() -> None:
    """Restart the OpenVPN service with systemctl"""
    try:
        logger.info("Restarting OpenVPN service...")
        import subprocess

        subprocess.run(
            ["/usr/bin/systemctl", "restart", "openvpn-server@server"],
            check=True,
            timeout=30,
        )
        logger.info("OpenVPN service restarted successfully.")
    except Exception:
        logger.error('OpenVPN restart failed')
        raise
