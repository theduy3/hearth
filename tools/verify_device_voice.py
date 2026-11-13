#!/usr/bin/env python3
"""Check a newly completed physical-device reply and its full-playback ACK."""
import argparse
import json
import re
import time
import urllib.request

from tools.provision_note4c import credential


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', required=True, type=float)
    args = parser.parse_args()
    opener = urllib.request.build_opener(NoRedirect())
    request = urllib.request.Request('https://zectrix.theduy.cloud/v1/device', headers={'Authorization': 'Bearer ' + credential()})
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        with opener.open(request, timeout=8) as response:
            data = json.loads(response.read(2049))
        record = data.get('request') or {}
        if (record.get('status') == 'completed' and record.get('speech_status') == 'delivered'
                and record.get('created', 0) >= args.since
                and re.fullmatch(r'[a-f0-9]{32}', record.get('client_id', ''))):
            print('DEVICE_VOICE_VERIFIED request=' + record['id'] + ' audio_ack=delivered')
            return
        time.sleep(1)
    raise RuntimeError('no new physical-device reply with successful full-playback acknowledgement')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Device voice check did not pass (' + type(error).__name__ + '). Retry after the complete spoken reply.', file=__import__('sys').stderr)
        raise SystemExit(1)
