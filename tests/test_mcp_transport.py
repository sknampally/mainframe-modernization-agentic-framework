"""Optional actual SDK/stdin transport checks against a local fixture, not AWS."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from kiro_workflow import Transform
from pilot import Blocked

@unittest.skipUnless(importlib.util.find_spec('mcp'), 'Install optional mcp SDK for local transport checks')
class MCPTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.client = Transform({'command': [sys.executable, str(Path(__file__).parent / 'fixtures/mcp_server.py')],
                                 'timeout_seconds': 30}, Path(temporary.name))

    def test_actual_sdk_and_nested_tool_envelope(self):
        result = self.client.calls([('get_status', {}), ('echo_required', {'value':'offline fixture'})])
        self.assertEqual(result, [{'connected':True, 'fixture':True}, {'echo':'offline fixture'}])

    def test_schema_missing_required_argument_is_refused(self):
        with self.assertRaises(Blocked):
            self.client.calls([('echo_required', {})])

if __name__ == '__main__':
    unittest.main()
