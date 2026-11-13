import contextlib
import io
import json
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from tools import provision_note4c as setup

MAC = '7c:4f:ad:b9:73:e0'


class FakeSerial:
    def __init__(self, **kwargs):
        self.port = None
        self.response = bytearray()
        self.written = b''
        self.closed = False
        self.open_count = 0
    def open(self): self.open_count += 1
    def reset_input_buffer(self): self.response.clear()
    def flush(self): pass
    def write(self, data):
        self.written += data
        result = {'ok': True, 'mac': MAC, 'configured': False}
        if data == b'CATTHEW_STATUS\n':
            result = {'ok': True, 'wifi': 0, 'clock': 0, 'frame_count': 0,
                      'password': 'private-test-password', 'token': 'private-test-token',
                      'http_status': 'unexpected private text'}
        self.response.extend(b'CATTHEW_CONFIG hidden-test-value\nCATTHEW_RESULT ' + json.dumps(result).encode() + b'\n')
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
            with setup.UsbDevice('/dev/test') as device:
                result = device.exchange('CATTHEW_INFO')
        self.assertTrue(result['ok'])
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(serial.written, b'CATTHEW_INFO\n')
        self.assertTrue(serial.closed)
        self.assertFalse(serial.dtr)
        self.assertFalse(serial.rts)

    def test_device_identity_checked_before_retrieving_credential(self):
        context = MagicMock()
        context.__enter__.return_value.exchange.return_value = {'ok': True, 'mac': 'wrong'}
        with patch('sys.argv', ['setup', 'pair']), patch.object(setup, 'UsbDevice', return_value=context), patch.object(setup, 'expected_mac', return_value=MAC), patch.object(setup, 'credential') as credential:
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

    def test_status_reuses_identity_connection_and_never_exposes_credentials(self):
        serial = FakeSerial()
        output = io.StringIO()
        with patch('sys.argv', ['setup', 'status']), patch.dict('sys.modules', {'serial': types.SimpleNamespace(Serial=Mock(return_value=serial))}), patch.object(setup, 'expected_mac', return_value=MAC), contextlib.redirect_stdout(output):
            setup.main()
        self.assertEqual(serial.open_count, 1)
        self.assertEqual(serial.written, b'CATTHEW_INFO\nCATTHEW_STATUS\n')
        self.assertEqual(json.loads(output.getvalue()), {'ok': True, 'wifi': 0, 'clock': 0, 'frame_count': 0})
        self.assertTrue(serial.closed)

    def test_info_outputs_only_public_setup_status(self):
        context = MagicMock()
        context.__enter__.return_value.exchange.return_value = {'ok': True, 'configured': False, 'mac': MAC, 'unexpected': 'private-test-value'}
        output = io.StringIO()
        with patch('sys.argv', ['setup', 'info']), patch.object(setup, 'UsbDevice', return_value=context), patch.object(setup, 'expected_mac', return_value=MAC), contextlib.redirect_stdout(output):
            setup.main()
        self.assertEqual(json.loads(output.getvalue()), {'ok': True, 'configured': False})

    def test_readiness_requires_wifi_time_and_successful_authenticated_frame(self):
        base = {'ok': True, 'wifi': 0, 'clock': 0, 'online': 0, 'frame_count': 0, 'frame_result': -1}
        states = [base, {**base, 'wifi': 1},
                  {**base, 'wifi': 1, 'clock': 1, 'online': 1, 'frame_count': 1, 'frame_result': 272},
                  {**base, 'wifi': 1, 'clock': 1, 'online': 1, 'frame_count': 2, 'frame_result': 0}]
        device = Mock()
        device.exchange.side_effect = states
        with patch.object(setup.time, 'sleep'), patch.object(setup.time, 'monotonic', side_effect=[0, 0, 1, 2, 3]):
            self.assertEqual(setup.wait_ready(device, 10), states[-1])
        self.assertEqual(device.exchange.call_count, 4)

    def test_missing_network_fails_readiness_instead_of_advancing_to_voice(self):
        device = Mock()
        device.exchange.return_value = {'ok': True, 'wifi': 0, 'clock': 0, 'frame_count': 0, 'wifi_reason': 201, 'password': 'private-test-value'}
        with patch.object(setup.time, 'sleep'), patch.object(setup.time, 'monotonic', side_effect=[0, 0, 2]), self.assertRaises(setup.DeviceNotReady) as caught:
            setup.wait_ready(device, 1)
        self.assertEqual(caught.exception.status['wifi_reason'], 201)
        self.assertNotIn('password', caught.exception.status)
