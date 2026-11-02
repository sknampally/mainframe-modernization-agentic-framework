"""Gate and evidence-integrity checks without Git commits, cloud calls, or models."""
import argparse
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('pilot', Path(__file__).parents[1] / 'scripts/pilot.py')
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace, self.source = self.root / 'workspace', self.root / 'source'
        self.workspace.mkdir()
        self.source.mkdir()
        (self.source / 'rule.cbl').write_text('IF AMOUNT = ZERO\n    MOVE 1 TO ERROR-FLAG\nEND-IF\n')
        self.revision = 'a' * 40
        self.dirty = False
        def git(root, *args):
            if args == ('rev-parse', 'HEAD'):
                return self.revision
            if args == ('remote', 'get-url', 'origin'):
                return 'https://example.invalid/public-source.git'
            if args == ('status', '--porcelain'):
                return ' M rule.cbl' if self.dirty else ''
            if args[0] == 'ls-files':
                return 'rule.cbl' if len(args) == 1 or args[-1] == 'rule.cbl' else ''
            raise AssertionError(args)
        self.mock = patch.object(pilot, 'git', side_effect=git)
        self.mock.start()
        self.addCleanup(self.mock.stop)
        self.args = argparse.Namespace(workspace=str(self.workspace), source=str(self.source), task_id='PILOT-TEST',
             owner='Test fixture', behavior='Reject zero amount', entrypoint='rule.cbl', max_operations=10, minutes=10)
        self.manifest = Path(pilot.init(self.args)['manifest'])
        self.directory = self.manifest.parent

    def run_command(self, command, role='executor', **kwargs):
        return pilot.operate(argparse.Namespace(command=command, task=str(self.manifest), role=role, **kwargs))

    def begin(self):
        return self.run_command('begin', actor='executor-session')

    def candidate(self):
        self.begin()
        self.run_command('read', path='rule.cbl', start=1, end=3)
        self.run_command('put', artifact='candidate', content='Candidate with rule and explicit uncertainty.')
        matrix = 'rule_id,source_path,source_commit,source_anchor,scenario_id,preconditions,input,expected_result,oracle,status\n'
        for index in range(3):
            matrix += f'RULE-1,rule.cbl,{self.revision},lines 1-3,S{index},fixture,zero,error flag,source,NOT RUN\n'
        self.run_command('put', artifact='traceability', content=matrix)
        return self.run_command('seal')

    def test_review_refuses_missing_executor_handoff(self):
        with self.assertRaisesRegex(pilot.Blocked, 'not READY'):
            self.run_command('begin', role='reviewer', actor='reviewer-session')

    def test_canonical_directory_and_pinned_manifest(self):
        task = json.loads(self.manifest.read_text())
        self.assertEqual(task['evidence_directory'], str(self.directory))
        self.assertEqual(task['source']['commit'], self.revision)
        self.assertFalse((self.workspace / 'candidate.md').exists())

    def test_manifest_edit_is_rejected(self):
        self.manifest.write_text(self.manifest.read_text() + ' ')
        with self.assertRaisesRegex(pilot.Blocked, 'Manifest changed'):
            self.begin()

    def test_dirty_or_changed_source_blocks(self):
        self.dirty = True
        with self.assertRaisesRegex(pilot.Blocked, 'not clean'):
            self.begin()
        self.dirty = False
        self.revision = 'b' * 40
        with self.assertRaisesRegex(pilot.Blocked, 'commit changed'):
            self.begin()

    def test_path_escape_is_rejected(self):
        self.begin()
        (self.root / 'secret.txt').write_text('do not read')
        with self.assertRaisesRegex(pilot.Blocked, 'escapes'):
            self.run_command('read', path='../secret.txt', start=1, end=1)

    def test_budget_has_no_role_restart(self):
        self.begin()
        for _ in range(9):
            self.run_command('read', path='rule.cbl', start=1, end=1)
        with self.assertRaisesRegex(pilot.Blocked, 'Budget exhausted'):
            self.run_command('read', path='rule.cbl', start=1, end=1)
        state = json.loads((self.directory / 'state.json').read_text())
        self.assertEqual(state['executor_status'], 'BLOCKED')
        self.assertEqual(state['sessions']['executor']['operations'], 10)
        with self.assertRaisesRegex(pilot.Blocked, 'already started'):
            self.begin()

    def test_deadline_blocks_sealing(self):
        self.begin()
        with patch.object(pilot.time, 'time', return_value=time.time() + 10000):
            with self.assertRaisesRegex(pilot.Blocked, 'Budget exhausted'):
                self.run_command('seal')

    def test_missing_candidate_cannot_be_sealed(self):
        self.begin()
        self.run_command('read', path='rule.cbl', start=1, end=1)
        with self.assertRaisesRegex(pilot.Blocked, 'artifact missing'):
            self.run_command('seal')

    def test_artifact_tampering_blocks_review(self):
        self.candidate()
        (self.directory / 'candidate.md').write_text('changed after sealing')
        with self.assertRaisesRegex(pilot.Blocked, 'missing or changed'):
            self.run_command('begin', role='reviewer', actor='reviewer-session')

    def test_handoff_tampering_blocks_review(self):
        self.candidate()
        path = self.directory / 'reviewer-handoff.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(pilot.Blocked, 'Handoff missing or changed'):
            self.run_command('begin', role='reviewer', actor='reviewer-session')

    def test_same_actor_cannot_review(self):
        self.candidate()
        with self.assertRaisesRegex(pilot.Blocked, 'separate session'):
            self.run_command('begin', role='reviewer', actor='executor-session')

    def test_untracked_source_file_cannot_be_read(self):
        self.begin()
        (self.source / 'untracked.txt').write_text('not in baseline')
        with self.assertRaisesRegex(pilot.Blocked, 'not tracked'):
            self.run_command('read', path='untracked.txt', start=1, end=1)

    def test_review_cannot_finish_without_primary_source_read(self):
        self.candidate()
        self.run_command('begin', role='reviewer', actor='reviewer-session')
        self.run_command('put', role='reviewer', artifact='review', content='Only read executor summary.')
        with self.assertRaisesRegex(pilot.Blocked, 'independently read'):
            self.run_command('finish-review', role='reviewer', decision='PASS')

    def test_reviewer_cannot_rewrite_candidate(self):
        self.candidate()
        self.run_command('begin', role='reviewer', actor='reviewer-session')
        with self.assertRaisesRegex(pilot.Blocked, 'not writable'):
            self.run_command('put', role='reviewer', artifact='candidate', content='reviewer replacement')

    def test_reinit_does_not_overwrite_an_attempt(self):
        with self.assertRaisesRegex(pilot.Blocked, 'already exists'):
            pilot.init(self.args)

    def test_valid_independent_handoff_never_supplies_human_approval(self):
        sealed = self.candidate()
        self.assertEqual(sealed['status'], 'READY_FOR_REVIEW')
        self.assertFalse(sealed['human_approved'])
        self.run_command('begin', role='reviewer', actor='separate-reviewer-session')
        self.run_command('read', role='reviewer', path='rule.cbl', start=1, end=3)
        self.run_command('put', role='reviewer', artifact='review', content='Inspected source; uncertainty requires correction.')
        result = self.run_command('finish-review', role='reviewer', decision='REWORK')
        self.assertEqual(result['decision'], 'REWORK')
        self.assertFalse(result['human_approved'])


if __name__ == '__main__':
    unittest.main()
