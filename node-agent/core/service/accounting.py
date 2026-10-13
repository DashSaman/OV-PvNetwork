"""Durable per-session counters, including the final OpenVPN disconnect sample."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat


def valid_sample(value):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',str(value.get('name',''))):return False
    if not re.fullmatch(r'[0-9A-Fa-f:.\[\]]{1,128}',str(value.get('remote',''))):return False
    return all(isinstance(value.get(key),int) and not isinstance(value[key],bool) and 0<=value[key]<2**63 for key in ['since','rx','tx'])


def status_samples(path,*,require_complete=False):
    try:text=Path(path).read_text(encoding='utf-8',errors='replace')
    except OSError:return None if require_complete else []
    return parse_status(text,require_complete=require_complete)


def parse_status(text,*,require_complete=False):
    lines=text.strip().splitlines()
    if require_complete and (not lines or lines[-1].strip()!='END'):return None
    header=None;values=[]
    for line in lines:
        parts=next(csv.reader([line],delimiter='\t' if '\t' in line else ','))
        if parts[:2]==['HEADER','CLIENT_LIST']:header=parts[2:];continue
        if not parts or parts[0]!='CLIENT_LIST':continue
        try:
            if header:
                fields=dict(zip(header,parts[1:]))
                value={'name':fields['Common Name'],'remote':fields['Real Address'],'since':int(fields['Connected Since (time_t)']),'rx':int(fields['Bytes Received']),'tx':int(fields['Bytes Sent'])}
                if fields.get('Client ID','').isdigit():value['client_id']=int(fields['Client ID'])
            else:
                value={'name':parts[1],'remote':parts[2],'since':int(parts[8]),'rx':int(parts[5]),'tx':int(parts[6])}
                if len(parts)>10 and parts[10].isdigit():value['client_id']=int(parts[10])
            if valid_sample(value):values.append(value)
        except (KeyError,IndexError,ValueError):continue
    return values


class UsageLedger:
    def __init__(self,path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink():raise ValueError('linked accounting database refused')
        with self.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY,name TEXT NOT NULL,rx INTEGER NOT NULL,tx INTEGER NOT NULL)')
        self.path.chmod(0o600)

    def connection(self):
        db=sqlite3.connect(self.path,timeout=10)
        db.execute('PRAGMA synchronous=FULL')
        return db

    def observe(self,samples):
        with self.connection() as db:
            for value in samples:
                if not valid_sample(value):raise ValueError('invalid accounting sample')
                identity=hashlib.sha256(json.dumps([value['name'],value['remote'],value['since']]).encode()).hexdigest()
                db.execute('INSERT INTO sessions VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET rx=max(rx,excluded.rx),tx=max(tx,excluded.tx)',(identity,value['name'],value['rx'],value['tx']))

    def consume_spool(self,directory):
        if not directory:return
        for path in sorted(Path(directory).glob('*.json'))[:4096]:
            descriptor=None
            try:
                descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
                info=os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_size>4096:continue
                value=json.loads(os.read(descriptor,4097));self.observe([value]);path.unlink()
            except (OSError,ValueError,TypeError):continue
            finally:
                if descriptor is not None:os.close(descriptor)

    def totals(self):
        users={};rx={};tx={}
        with self.connection() as db:
            for name,received,sent in db.execute('SELECT name,SUM(rx),SUM(tx) FROM sessions GROUP BY name'):
                users[name]=received+sent;rx[name]=received;tx[name]=sent
        return {'users':users,'users_rx':rx,'users_tx':tx}
