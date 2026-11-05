import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = {'pbs-report.py': (ROOT / 'pbs-report.py').read_bytes(), 'systemd/guest.conf': (ROOT / 'systemd/guest.conf').read_bytes(), 'systemd/host.conf': (ROOT / 'systemd/host.conf').read_bytes()}
DEST = ['usr/local/sbin/pbs-report', 'etc/systemd/system/pbs-guarded-backup.service.d/20-discord-report.conf', 'etc/systemd/system/pve-host-config-backup.service.d/20-discord-report.conf']

class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / 'release.tar.gz'
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, data in FILES.items():
                item = tarfile.TarInfo(name); item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.bin = self.root / 'bin'; self.bin.mkdir()
        for name, content in {'pveversion': 'exit 0', 'perl': 'exit 0', 'systemctl': '''
case "$1" in
 show) case "$*" in *LoadState*) [ "${MISSING:-0}" = 0 ] && echo loaded || echo not-found ;; *ActiveState*) echo "${ACTIVE_STATE:-inactive}" ;; *ExecStopPost*) case "$2" in pbs-guarded*) kind=guest ;; *) kind=host ;; esac; echo "path=/usr/bin/timeout ; argv[]=/usr/bin/timeout 30 /usr/bin/python3 /usr/local/sbin/pbs-report $kind ; ignore_errors=yes" ;; esac ;;
 is-active) exit 3 ;;
 daemon-reload) [ "${FAIL_RELOAD:-0}" = 0 ] ;;
esac'''}.items():
            path = self.bin / name; path.write_text('#!/bin/sh\n' + content + '\n'); path.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + ':' + os.environ['PATH'], PVE_REPORT_TEST_ROOT=str(self.root / 'target'))
    def run_install(self, sha=None, **env):
        return subprocess.run(['sh', str(ROOT / 'install.sh'), str(self.archive), sha or self.sha], env=dict(self.env, **env), capture_output=True, text=True)
    def test_checksum_and_preflight_do_not_write(self):
        self.assertNotEqual(self.run_install('0' * 64).returncode, 0)
        self.assertNotEqual(self.run_install(MISSING='1').returncode, 0)
        self.assertNotEqual(self.run_install(ACTIVE_STATE='activating').returncode, 0)
        self.assertFalse((self.root / 'target').exists())
    def test_install_and_rollback_existing_files(self):
        result = self.run_install(); self.assertEqual(result.returncode, 0, result.stderr)
        target = self.root / 'target'
        for i, name in enumerate(DEST):
            (target / name).write_bytes(('old-%s' % i).encode())
            (target / name).chmod(0o640)
        before = [(target / name).read_bytes() for name in DEST]
        result = self.run_install(FAIL_RELOAD='1'); self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, [(target / name).read_bytes() for name in DEST])
        self.assertTrue(all((target / name).stat().st_mode & 0o777 == 0o640 for name in DEST))
    def test_archive_and_destination_symlinks_rejected(self):
        with tarfile.open(self.archive, 'w:gz') as archive:
            item = tarfile.TarInfo('../escape'); item.size = 1
            archive.addfile(item, io.BytesIO(b'x'))
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse((self.root / 'target').exists())
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, data in FILES.items():
                item = tarfile.TarInfo(name); item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
        self.sha = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        target = self.root / 'target'; target.mkdir()
        (target / 'usr').symlink_to(self.root / 'elsewhere')
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse((self.root / 'elsewhere').exists())
    def test_rollback_first_install(self):
        result = self.run_install(FAIL_RELOAD='1'); self.assertNotEqual(result.returncode, 0)
        self.assertTrue(all(not (self.root / 'target' / name).exists() for name in DEST))

if __name__ == '__main__': unittest.main()
