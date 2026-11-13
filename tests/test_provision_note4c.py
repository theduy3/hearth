import contextlib
import io
import json
import types
import unittest
from unittest.mock import Mock, patch

from tools import provision_note4c as setup


class FakeSerial:
    def __init__(self, **kwargs):
        self.port = None
        self.response = bytearray(b'CATTHEW_CONFIG hidden-test-value\nCATTHEW_RESULT {"ok":true,"configured":false}\n')
        self.written = b''
        self.closed = False
    def open(self): pass
    def reset_input_buffer(self): pass
    def flush(self): pass
    def write(self, data): self.written += data
    def close(self): self.closed = True
    def read(self, count):
        data = self.response[:count]
        del self.response[:count]
        return bytes(data)


class ProvisioningTests(unittest.TestCase):
    def test_serial_echo_is_ignored_and_never_logged(self):
        serial = FakeSerial()
        output = io.StringIO()
        with patch.dict('sys.modules', {'serial': types.SimpleNamespace(Serial=Mock(return_value=serial))}), contextlib.redirect_stdout(output):
            result = setup.exchange('/dev/test', 'CATTHEW_INFO')
        self.assertTrue(result['ok'])
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(serial.written, b'CATTHEW_INFO\n')
        self.assertTrue(serial.closed)
        self.assertFalse(serial.dtr)
        self.assertFalse(serial.rts)

    def test_device_identity_checked_before_retrieving_credential(self):
        with patch('sys.argv', ['setup', 'pair']), patch.object(setup, 'exchange', return_value={'ok': True, 'mac': 'wrong'}), patch.object(setup, 'expected_mac', return_value='7c:4f:ad:b9:73:e0'), patch.object(setup, 'credential') as credential:
            with self.assertRaises(RuntimeError):
                setup.main()
            credential.assert_not_called()

    def test_ssh_credential_is_captured_without_output(self):
        token = 'private-test-token-' + 'a' * 32
        output = io.StringIO()
        result = types.SimpleNamespace(stdout=json.dumps({'token': token}))
        with patch.object(setup.subprocess, 'run', return_value=result) as run, contextlib.redirect_stdout(output):
            self.assertEqual(setup.credential(), token)
        self.assertEqual(output.getvalue(), '')
        self.assertTrue(run.call_args.kwargs['capture_output'])
        self.assertNotIn(token, repr(run.call_args.args))

    def test_info_outputs_only_public_setup_status(self):
        output = io.StringIO()
        info = {'ok': True, 'configured': False, 'mac': '7c:4f:ad:b9:73:e0', 'unexpected': 'private-test-value'}
        with patch('sys.argv', ['setup', 'info']), patch.object(setup, 'exchange', return_value=info), patch.object(setup, 'expected_mac', return_value=info['mac']), contextlib.redirect_stdout(output):
            setup.main()
        self.assertEqual(json.loads(output.getvalue()), {'ok': True, 'configured': False})
