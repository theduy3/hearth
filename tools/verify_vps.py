#!/usr/bin/env python3
"""Read-only release checks for the approved Bluehost Catthew deployment."""
import argparse
import json
import subprocess
from urllib.error import HTTPError
from urllib.request import urlopen

REMOTE = r'''
import hashlib,json,http.client
from pathlib import Path
from urllib.request import urlopen
import yaml
from hub.gateway import Gateway
from hub.settings import setting
root=Path('/home/hermes/.hermes')
profile=root/'profiles/catthew'
c=yaml.safe_load((profile/'config.yaml').read_text())
raw=(root/'catthew-terminal-state/terminal.env').read_text()
checks={'model':c.get('model',{}).get('default')=='gpt-6.1-sol',
        'provider':c.get('model',{}).get('provider')=='openai-codex',
        'soul_sha256':hashlib.sha256((profile/'SOUL.md').read_bytes()).hexdigest()}
try:
 Gateway(setting(raw,'HEARTH_HERMES_URL'),setting(raw,'HEARTH_HERMES_KEY'))._assert_household_policy()
 checks['household_policy']=True
except Exception:checks['household_policy']=False
with urlopen('http://127.0.0.1:8791/health',timeout=5) as response:
 checks['speech_service']=response.status==200
state=json.loads((root/'gateway_state.json').read_text())
checks['catthew_telegram']=state.get('platforms',{}).get('catthew:telegram',{}).get('state')=='connected'
connection=http.client.HTTPSConnection('zectrix.theduy.cloud',timeout=15)
connection.request('GET','/v1/frame?page=today',headers={'Authorization':'Bearer '+setting(raw,'HEARTH_DEVICE_TOKEN')})
response=connection.getresponse();pixels=response.read(30001)
checks['authenticated_color_frame']=response.status==200 and len(pixels)==30000 and response.getheader('ETag')=='"'+hashlib.sha256(pixels).hexdigest()+'"'
connection.close()
owned=[]
for path in Path('/proc').iterdir():
 if not path.name.isdigit():continue
 try:
  if (path/'cmdline').read_bytes().split(bytes([0]))[1:3]==[b'-m',b'hub.terminal']:
   owned.append('catthew-terminal.service' in (path/'cgroup').read_text())
 except OSError:pass
checks['owned_single_service_process']=owned==[True]
print(json.dumps(checks))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soul-sha256", required=True)
    args = parser.parse_args()
    checks = {}
    with urlopen("https://zectrix.theduy.cloud/health", timeout=15) as response:
        checks["verified_https_health"] = response.status == 200 and json.load(response).get("ok") is True
    try:
        with urlopen("https://zectrix.theduy.cloud/v1/poster", timeout=10):
            checks["unauthorized_rejected"] = False
    except HTTPError as error:
        checks["unauthorized_rejected"] = error.code == 401
        error.close()
    command = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "bluehost", "docker", "exec", "-i", "--user", "1500",
               "--workdir", "/home/hermes/.hermes/catthew-terminal", "hermes",
               "/home/hermes/.hermes/hermes-agent/venv/bin/python", "-"]
    result = subprocess.run(command, input=REMOTE, text=True, capture_output=True, check=True, timeout=30)
    remote = json.loads(result.stdout)
    services = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "bluehost", "systemctl", "is-active", "catthew-terminal.service", "catthew-speech.service"], text=True, capture_output=True, timeout=15)
    checks["supervised_services_active"] = services.returncode == 0 and services.stdout.split() == ["active", "active"]
    checks["soul_unchanged"] = remote.pop("soul_sha256") == args.soul_sha256
    checks.update(remote)
    print(json.dumps(checks, sort_keys=True))
    if not all(value is True for value in checks.values()):
        raise SystemExit(1)
    print("VPS_VERIFIED")


if __name__ == "__main__":
    main()
