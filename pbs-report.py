#!/usr/bin/python3
import datetime, os, re, socket, subprocess, sys

def extract(pattern, text, default='N/A'):
    m = re.search(pattern, text, re.M)
    return m.group(1).strip() if m else default

def render(kind, log, result, end):
    if kind == 'host' and result == 'exec-condition':
        return None
    if kind == 'guest' and 'PBS unavailable; backup skipped:' in log:
        return None
    failed = result != 'success' or (kind == 'host' and 'Starting backup:' not in log) or bool(re.search(r'ERROR: (?:Backup of VM|Backup job)', log))
    status = 'FAILED' if failed else 'OK'
    if kind == 'host':
        start = extract(r'Starting backup protocol: (.+)', log)
        rates = re.findall(r'^(etc|pve-config)\.pxar:.*?\(average ([^)]+)\)', log, re.M)
        details = [f'{name}: {rate}' for name,rate in rates] or ['Speed: N/A']
    else:
        starts = re.findall(r'Backup started at (.+)', log)
        start = starts[0] if starts else 'N/A'
        details = []
        parts = []
        for part in re.split(r'(?=INFO: Starting Backup of VM \d+)', log)[1:]:
            vmid = extract(r'Starting Backup of VM (\d+)', part)
            if parts and parts[-1][0] == vmid:
                parts[-1] = (vmid, parts[-1][1] + part)
            else:
                parts.append((vmid, part))
        for vmid, part in parts:
            name = extract(r'(?:VM|CT) Name: (.+)',part, '')[:22]
            rate = extract(r'transferred [^\n]+ \(([^)]+/s)\)',part)
            if rate == 'N/A': rate = extract(r'root\.pxar:.*?\(average ([^)]+)\)',part)
            outcome = 'FAIL' if re.search(r'ERROR: Backup of VM',part) else ('OK' if 'Finished Backup of VM' in part else '?')
            begin = extract(r'Backup started at (.+)',part)
            finish = extract(r'Backup (?:finished|failed) at (.+)',part)
            details.extend([f'{vmid} {name} | {outcome} | {rate}', f'  {begin} -> {finish}'])
        if not details: details = ['Guest details unavailable']
    rows = [f'Status  | {status}',f'Start   | {start}',f'End     | {end}'] + details
    return f'{kind.upper()} BACKUP ({socket.gethostname()})\n```\n'+'\n'.join(rows)+'\n```\nSpeed: processed data, not network throughput.'

def main():
    kind = sys.argv[1]
    invocation = os.environ['INVOCATION_ID']
    log = subprocess.check_output(['journalctl','--no-pager','-o','cat','_SYSTEMD_INVOCATION_ID='+invocation],text=True)
    result = os.environ.get('SERVICE_RESULT','unknown')
    end = datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')
    msg = render(kind,log,result,end)
    if msg is None:
        print('PBS skip: notification suppressed')
        return
    if os.environ.get('PBS_REPORT_TEST'):
        msg = '[TEST - historical data] ' + msg
    perl = r'''my $s=do {local $/; <STDIN>}; my $d=PVE::Notify::common_template_data(); $d->{"status-text"}=$s; $d->{"guest-table"}={schema=>{columns=>[{label=>"Status",id=>"s"}]},data=>[{s=>"report"}]}; $d->{"total-size"}=0; $d->{"total-time"}=0; $d->{logs}=""; chomp(my $host=`hostname`); PVE::Notify::notify($ARGV[0],"vzdump",$d,{type=>"vzdump",hostname=>$host});'''
    subprocess.run(['perl','-MPVE::Notify','-e',perl,'error' if 'Status  | FAILED' in msg else 'info'], input=msg, text=True, check=True)

if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        assert render('host','','exec-condition','end') is None
        assert render('guest','PBS unavailable; backup skipped: timeout','success','end') is None
        assert 'FAILED' in render('host','','exit-code','end')
        assert '3 MiB/s' in render('host','Starting backup: host/a\nStarting backup protocol: now\netc.pxar: abc (average 3 MiB/s)','success','end')
        data='INFO: Starting Backup of VM 104 (qemu)\nINFO: Backup started at TODAY\nINFO: VM Name: Jellyfin\nINFO: transferred 2 GiB in 1 seconds (2 MiB/s)\nINFO: Finished Backup of VM 104 (00:00:01)'
        assert '104 Jellyfin | OK | 2 MiB/s' in render('guest',data,'success','end')
        assert render('guest','INFO: Starting Backup of VM 104 (qemu)\n'+data,'success','end').count('104 Jellyfin') == 1
        assert 'FAILED' in render('guest',data+'\nERROR: Backup of VM 104 failed', 'success','end')
        print('self-test passed')
    else: main()
