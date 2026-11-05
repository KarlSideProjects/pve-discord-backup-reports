#!/usr/bin/python3
import datetime, json, os, re, socket, subprocess, sys


def extract(pattern, text, default='N/A'):
    match = re.search(pattern, text, re.M)
    return match.group(1).strip() if match else default


def build_report(kind, log, result, end, hostname):
    if kind == 'host' and result == 'exec-condition' and 'Starting backup:' not in log:
        return None
    if kind == 'guest' and result == 'success' and re.search(r'^PBS unavailable; backup skipped:', log, re.M) and not re.search(r'(?:Starting Backup of VM|ERROR: Backup)', log):
        return None
    failed = result != 'success' or bool(re.search(r'ERROR: (?:Backup of VM|Backup job)', log))
    entries = []
    if kind == 'host':
        start = extract(r'Starting backup protocol: (.+)', log)
        for name, rate in re.findall(r'^(etc|pve-config)\.pxar:.*?\(average ([^)]+)\)', log, re.M):
            entries.append({'name': name, 'status': 'OK', 'speed': rate})
        finish = extract(r'^End Time: (.+)', log)
        uncertain = 'Starting backup:' not in log or start == 'N/A' or finish == 'N/A' or {x['name'] for x in entries} != {'etc', 'pve-config'}
    else:
        starts = re.findall(r'Backup started at (.+)', log)
        start = starts[0] if starts else 'N/A'
        parts = []
        for part in re.split(r'(?=INFO: Starting Backup of VM \d+)', log)[1:]:
            vmid = extract(r'Starting Backup of VM (\d+)', part)
            if parts and parts[-1][0] == vmid:
                parts[-1] = (vmid, parts[-1][1] + part)
            else:
                parts.append((vmid, part))
        failed_ids = set(re.findall(r'ERROR: Backup of VM (\d+)', log))
        for vmid, part in parts:
            speed = extract(r'transferred [^\n]+ \(([^)]+/s)\)', part)
            if speed == 'N/A': speed = extract(r'root\.pxar:.*?\(average ([^)]+)\)', part)
            status = 'FAILED' if vmid in failed_ids else ('OK' if 'Finished Backup of VM' in part else 'UNKNOWN')
            start_time = extract(r'Backup started at (.+)', part)
            finish_time = extract(r'Backup (?:finished|failed) at (.+)', part)
            if status == 'OK' and 'N/A' in (start_time, finish_time, speed): status = 'UNKNOWN'
            entries.append({'name': vmid + ' ' + extract(r'(?:VM|CT) Name: (.+)', part, ''), 'status': status, 'speed': speed,
                            'start': start_time, 'end': finish_time})
        for vmid in sorted(failed_ids - {part[0] for part in parts}):
            entries.append({'name': vmid + ' ', 'status': 'FAILED', 'speed': 'N/A', 'start': 'N/A', 'end': 'N/A'})
        uncertain = not entries or any(item['status'] == 'UNKNOWN' for item in entries)
    status = 'FAILED' if failed or any(item['status'] == 'FAILED' for item in entries) else ('UNKNOWN' if uncertain else 'OK')
    return {'kind': kind, 'status': status, 'host': hostname, 'start': start, 'end': end, 'finish': finish if kind == 'host' else None, 'entries': entries}


def notification_severity(status):
    return 'info' if status == 'OK' else 'error'


def embed_payload(report):
    icons = {'OK': '🟢', 'FAILED': '🔴', 'UNKNOWN': '🟡'}
    labels = {'OK': '成功', 'FAILED': '失敗', 'UNKNOWN': '資料不足'}
    colors = {'OK': 3066993, 'FAILED': 15158332, 'UNKNOWN': 15844367}
    status = report['status']
    title = f"{icons[status]} {'VM／CT' if report['kind'] == 'guest' else '主機'}備份：{labels[status]}"[:256]
    description = f"**主機**：{report['host'][:100]}\n**開始**：{report['start'][:100]}\n**報告時間**：{report['end'][:100]}"
    if report['kind'] == 'host': description += f"\n**結束**：{report['finish'][:100]}"
    fields = []
    ordered = sorted(report['entries'], key=lambda item: item['status'] != 'FAILED')
    for entry in ordered[:20]:
        name = entry['name'].strip()[:100] or '未知項目'
        entry_status = entry['status']
        value = f"處理速度 {entry['speed'][:80]}"
        if report['kind'] == 'guest': value = f"{icons[entry_status]} {labels[entry_status]} · " + value
        if report['kind'] == 'guest': value += f"\n開始：{entry['start'][:100]}\n結束：{entry['end'][:100]}"
        fields.append({'name': name, 'value': value[:1024], 'inline': False})
    if ordered and report['kind'] == 'guest': description += f"\n**失敗 {sum(x['status'] == 'FAILED' for x in ordered)} · 資料不足 {sum(x['status'] == 'UNKNOWN' for x in ordered)}**"
    if not ordered: description += '\n⚠️ 沒有可解析的備份明細。'
    # Keep a conservative budget below Discord's combined 6000-character limit.
    utf16 = lambda value: len(value.encode('utf-16-le')) // 2
    while sum(utf16(x['name']) + utf16(x['value']) for x in fields) + utf16(title) + utf16(description) > 4800:
        fields.pop()
    if len(ordered) > len(fields): description += f"\n⚠️ 已省略 {len(ordered) - len(fields)} 個項目，請查看主機日誌。"
    return {'allowed_mentions': {'parse': []}, 'embeds': [{'title': title, 'description': description, 'color': colors[status], 'fields': fields,
             'footer': {'text': '處理速度非網路吞吐量；報告成功不代表備份可還原。'}}]}


def main():
    kind = sys.argv[1]
    log = subprocess.check_output(['journalctl','--no-pager','-o','cat','_SYSTEMD_INVOCATION_ID='+os.environ['INVOCATION_ID']], text=True)
    end = datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    report = build_report(kind, log, os.environ.get('SERVICE_RESULT','unknown'), end, socket.gethostname())
    if report is None:
        print('PBS skip: notification suppressed')
        return
    payload = embed_payload(report)
    if os.environ.get('PBS_REPORT_TEST'): payload['content'] = '[TEST - historical data]'
    fallback = f"{kind.upper()} BACKUP ({report['host']}): {report['status']} | Start: {report['start']} | Report: {end}"
    data = json.dumps({'fallback': fallback, 'report_json': json.dumps(payload, ensure_ascii=True)}, ensure_ascii=True)
    perl = r'''use JSON::PP; my $in=decode_json(do {local $/; <STDIN>}); my $d=PVE::Notify::common_template_data(); $d->{"status-text"}=$in->{fallback}; $d->{"guest-table"}={schema=>{columns=>[{label=>"Status",id=>"s"}]},data=>[{s=>"report"}]}; $d->{"total-size"}=0; $d->{"total-time"}=0; $d->{logs}=""; chomp(my $host=`hostname`); PVE::Notify::notify($ARGV[0],"vzdump",$d,{type=>"vzdump",hostname=>$host,report_json=>$in->{report_json}});'''
    subprocess.run(['perl','-MPVE::Notify','-e',perl,notification_severity(report['status'])], input=data, text=True, check=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        assert build_report('host','','exec-condition','end','test') is None
        assert build_report('guest','PBS unavailable; backup skipped: timeout','success','end','test') is None
        assert build_report('guest','','success','end','test')['status'] == 'UNKNOWN'
        assert embed_payload(build_report('host','Starting backup: test','success','end','test'))['embeds'][0]['title']
        print('self-test passed')
    else: main()
