import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('report', Path(__file__).resolve().parents[1] / 'pbs-report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

GUEST = '''INFO: Starting Backup of VM 104 (qemu)
INFO: Backup started at 2026-11-05 19:12:41
INFO: VM Name: Jellyfin
INFO: transferred 2 GiB in 1 seconds (2 MiB/s)
INFO: Backup finished at 2026-11-05 19:12:49
INFO: Finished Backup of VM 104 (00:00:01)
'''

class ReportTests(unittest.TestCase):
    def test_separate_guest_embed_fields(self):
        obj = report.build_report('guest', GUEST, 'success', 'END', 'node')
        self.assertEqual(obj['status'], 'OK')
        payload = report.embed_payload(obj)
        self.assertEqual(payload['allowed_mentions'], {'parse': []})
        fields = payload['embeds'][0]['fields']
        entry = next(x for x in fields if '104' in x['name'])
        self.assertIn('Jellyfin', entry['name'])
        self.assertIn('2 MiB/s', entry['value'])
        self.assertIn('19:12:49', entry['value'])
        self.assertNotIn('```', entry['value'])
    def test_failed_unknown_skip(self):
        self.assertIsNone(report.build_report('guest', 'PBS unavailable; backup skipped: offline', 'success', 'END', 'node'))
        self.assertEqual(report.build_report('guest', '', 'success', 'END', 'node')['status'], 'UNKNOWN')
        self.assertEqual(report.notification_severity('UNKNOWN'), 'error')
        self.assertEqual(report.build_report('guest', GUEST.replace('Finished Backup of VM', 'Missing Backup of VM'), 'success', 'END', 'node')['status'], 'UNKNOWN')
        self.assertEqual(report.build_report('guest', GUEST+'ERROR: Backup of VM 104 failed', 'success', 'END', 'node')['status'], 'FAILED')
    def test_skip_does_not_hide_failure_or_started_backup(self):
        skip = 'PBS unavailable; backup skipped: offline\n'
        self.assertEqual(report.build_report('guest', skip, 'exit-code', 'END', 'node')['status'], 'FAILED')
        self.assertEqual(report.build_report('guest', skip + 'ERROR: Backup of VM 104 failed\n', 'success', 'END', 'node')['status'], 'FAILED')
        self.assertEqual(report.build_report('guest', skip + GUEST, 'success', 'END', 'node')['status'], 'OK')
        self.assertEqual(report.build_report('host', 'Starting backup: host/a', 'exec-condition', 'END', 'node')['status'], 'FAILED')

    def test_long_report_limited_preserves_failures(self):
        raw = ''.join(GUEST.replace('104', str(i)).replace('Jellyfin', 'A' * 400) for i in range(100,140))
        raw += GUEST.replace('104','999') + 'ERROR: Backup of VM 999 failed\n'
        obj = report.build_report('guest',raw,'success','END','node')
        data = report.embed_payload(obj)
        embed = data['embeds'][0]
        self.assertLessEqual(len(embed['fields']),25)
        self.assertTrue(any('999' in x['name'] for x in embed['fields']))
        self.assertIn(f"已省略 {len(obj['entries']) - len(embed['fields'])} 個項目", embed['description'])
        self.assertIn('失敗 1', embed['description'])
        self.assertLessEqual(sum(len(embed.get(k,'')) for k in ('title','description')) + sum(len(f['name'])+len(f['value']) for f in embed['fields']) + len(embed['footer']['text']),6000)
        self.assertTrue(all(len(x['name']) <= 256 and len(x['value']) <= 1024 for x in embed['fields']))
        json.dumps(data, ensure_ascii=False)
    def test_unicode_lengths_fit_discord(self):
        raw = ''.join(GUEST.replace('104', str(i)).replace('Jellyfin', '😀' * 300).replace('2026-11-05 19:12:41', '😀' * 100) for i in range(20))
        embed = report.embed_payload(report.build_report('guest',raw,'success','😀' * 100,'😀' * 100))['embeds'][0]
        count = lambda x: len(x.encode('utf-16-le')) // 2
        self.assertLessEqual(count(embed['title']) + count(embed['description']) + count(embed['footer']['text']) + sum(count(x['name']) + count(x['value']) for x in embed['fields']),6000)
    def test_delayed_error_is_attributed_to_the_right_vm(self):
        raw = GUEST + GUEST.replace('104','105').replace('Jellyfin','Wireguard') + 'ERROR: Backup of VM 104 failed\n'
        items = report.build_report('guest', raw, 'success', 'END', 'node')['entries']
        by_id = {item['name'].split()[0]: item['status'] for item in items}
        self.assertEqual(by_id['104'], 'FAILED')
        self.assertEqual(by_id['105'], 'OK')

    def test_failure_without_start_line_keeps_failed_id_visible(self):
        raw = GUEST + 'ERROR: Backup of VM 999 failed\n'
        items = report.build_report('guest', raw, 'success', 'END', 'node')['entries']
        self.assertTrue(any(item['name'].startswith('999 ') and item['status'] == 'FAILED' for item in items))

    def test_missing_time_or_speed_is_not_complete_success(self):
        self.assertEqual(report.build_report('guest', GUEST.replace('Backup finished at', 'unknown time'), 'success', 'END', 'node')['status'], 'UNKNOWN')
        self.assertEqual(report.build_report('guest', GUEST.replace('(2 MiB/s)', '(missing)'), 'success', 'END', 'node')['status'], 'UNKNOWN')
        self.assertEqual(report.build_report('host', 'Starting backup: host/a', 'success', 'END', 'node')['status'], 'UNKNOWN')

    def test_host_success_and_unverified(self):
        log = 'Starting backup: host/a\nStarting backup protocol: now\netc.pxar: abc (average 3 MiB/s)\npve-config.pxar: abc (average 2 MiB/s)\nEnd Time: finished'
        obj = report.build_report('host', log, 'success', 'END', 'node')
        self.assertEqual(obj['status'], 'OK')
        self.assertIn('3 MiB/s', str(report.embed_payload(obj)))
        self.assertIn('結束**：finished', report.embed_payload(obj)['embeds'][0]['description'])
        self.assertEqual(report.build_report('host', log.replace('End Time: finished', ''), 'success', 'END', 'node')['status'], 'UNKNOWN')
        self.assertEqual(report.build_report('host', log.replace('pve-config.pxar:', 'missing:'), 'success', 'END', 'node')['status'], 'UNKNOWN')
        failed = report.embed_payload(report.build_report('host', log, 'exit-code', 'END', 'node'))['embeds'][0]
        self.assertNotIn('成功', failed['fields'][0]['value'])
        self.assertNotIn('失敗 0', failed['description'])
        self.assertIn('3 MiB/s', failed['fields'][0]['value'])
        self.assertIsNone(report.build_report('host','','exec-condition','END','node'))

if __name__ == '__main__': unittest.main()
