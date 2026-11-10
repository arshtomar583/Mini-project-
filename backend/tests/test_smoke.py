"""Regression checks for startup races in the deployment verifier."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location('smoke_deployment', Path(__file__).resolve().parents[2] / 'scripts/smoke_deployment.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeReadinessTests(unittest.TestCase):
    def test_docker_connection_reset_and_non_json_startup_response_are_retried(self):
        request = Mock(side_effect=[ConnectionResetError('Server still starting'),
                                    (200, {}, b'Loading'), (200, {}, b'{"status":"ok"}')])
        with patch.object(smoke.time, 'sleep'):
            smoke.wait_for_health(request, 30)
        self.assertEqual(request.call_count, 3)
        self.assertTrue(all(call.args == ('/health',) for call in request.call_args_list))

    def test_unready_server_stops_at_deadline(self):
        request = Mock(side_effect=ConnectionResetError('Not ready'))
        with patch.object(smoke.time, 'monotonic', side_effect=[0, 31]), patch.object(smoke.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'did not become ready'):
                smoke.wait_for_health(request, 30)
        sleep.assert_not_called()
