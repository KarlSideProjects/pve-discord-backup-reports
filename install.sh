#!/bin/sh
# Install only a locally downloaded release archive after verifying its pinned SHA-256.
exec python3 - "$@" <<'PY'
import hashlib
import io
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

sources = ('pbs-report.py', 'systemd/guest.conf', 'systemd/host.conf')
destinations = ('usr/local/sbin/pbs-report', 'etc/systemd/system/pbs-guarded-backup.service.d/20-discord-report.conf', 'etc/systemd/system/pve-host-config-backup.service.d/20-discord-report.conf')
units = ('pbs-guarded-backup.service', 'pve-host-config-backup.service')
root = Path(os.environ.get('PVE_REPORT_TEST_ROOT', '/'))

def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

def main():
    if len(sys.argv) != 3 or not re.fullmatch(r'[0-9a-fA-F]{64}', sys.argv[2]):
        raise ValueError('Usage: sh install.sh RELEASE.tar.gz SHA256')
    if os.geteuid() != 0 and str(root) == '/':
        raise ValueError('Run as root on the target PVE')
    data = Path(sys.argv[1]).read_bytes()
    if hashlib.sha256(data).hexdigest() != sys.argv[2].lower():
        raise ValueError('Archive checksum mismatch; no files changed')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        members = tar.getmembers()
        if len(members) != 3 or set(m.name for m in members) != set(sources) or any(not m.isfile() or m.size > 1000000 for m in members):
            raise ValueError('Archive must contain only the three expected regular files')
        contents = [tar.extractfile(name).read() for name in sources]
    run('pveversion')
    run('perl', '-MPVE::Notify', '-e', '1')
    for unit in units:
        if run('systemctl', 'show', unit, '-p', 'LoadState', '--value') != 'loaded':
            raise ValueError('Required service is not loaded: ' + unit)
        active = run('systemctl', 'show', unit, '-p', 'ActiveState', '--value')
        if active not in ('inactive', 'failed'):
            raise ValueError('Backup service is not stopped: ' + unit + ' (' + active + ')')
    for tool in ('timeout', 'journalctl'):
        if not shutil.which(tool): raise ValueError('Missing dependency: ' + tool)
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / 'pbs-report.py'; report.write_bytes(contents[0])
        run('python3', str(report), '--self-test')
    for rel in destinations:
        path = root / rel
        for part in (path, *path.parents):
            if part == root.parent:
                break
            if part.is_symlink():
                raise ValueError('Symlink in destination path: ' + str(part))
        if path.exists() and not path.is_file():
            raise ValueError('Destination is not a regular file: ' + str(path))
    backup_parent = root / 'root'
    backup_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = Path(tempfile.mkdtemp(prefix='pbs-report-rollback.', dir=backup_parent))
    absent = []
    for rel in destinations:
        path = root / rel
        if path.exists():
            saved = backup / rel; saved.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(path, saved)
        else:
            absent.append(rel)
    (backup / 'absent').write_text(''.join(x + '\n' for x in absent))
    print('Rollback directory:', backup, flush=True)
    try:
        for i, rel in enumerate(destinations):
            dest = root / rel; dest.parent.mkdir(parents=True, exist_ok=True)
            fd, name = tempfile.mkstemp(prefix='.pbs-report-', dir=dest.parent)
            try:
                with os.fdopen(fd, 'wb') as out: out.write(contents[i])
                os.chmod(name, 0o755 if i == 0 else 0o644)
                os.replace(name, dest)
            finally:
                if os.path.exists(name): os.unlink(name)
        run('systemctl', 'daemon-reload')
        for unit, kind in zip(units, ('guest', 'host')):
            hooks = run('systemctl', 'show', unit, '-p', 'ExecStopPost', '--value')
            expected = 'path=/usr/bin/timeout ; argv[]=/usr/bin/timeout 30 /usr/bin/python3 /usr/local/sbin/pbs-report ' + kind + ' ; ignore_errors=yes'
            if expected not in hooks:
                raise ValueError('Expected report hook missing from ' + unit)
        for i, rel in enumerate(destinations):
            if (root / rel).read_bytes() != contents[i]: raise ValueError('Installed file verification failed: ' + rel)
    except BaseException:
        failures = []
        for rel in destinations:
            try:
                path = root / rel; saved = backup / rel
                if rel in absent: path.unlink(missing_ok=True)
                else: shutil.copy2(saved, path)
            except Exception as exc: failures.append(str(exc))
        try: run('systemctl', 'daemon-reload')
        except Exception as exc: failures.append('daemon-reload: ' + str(exc))
        if failures: print('Rollback incomplete; use backup directory:', '; '.join(failures), file=sys.stderr)
        raise
    print('Installed; no backups or notifications were started.')

try:
    main()
except Exception as exc:
    print('Installation failed:', exc, file=sys.stderr)
    sys.exit(1)
PY
