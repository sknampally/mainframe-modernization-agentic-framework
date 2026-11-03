"""User-facing command defaults and setup recovery; no cloud/model calls."""
import argparse
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import modernize as app
import modernize_setup as guide
from pilot import Blocked

class GuidedTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.work=Path(temp.name)
        mock=patch.object(guide,'active_file',return_value=self.work/'config/active.json')
        mock.start();self.addCleanup(mock.stop)
        self.project={'stage':'READY_TO_ASSESS','assessments':{},'source':{'root':'/fixture/source','repository':'https://github.com/example/source.git'},
            'providers':{'executor':'claude','wireframes':'codex'},'aws':{'profile':'fixture','region':'us-east-1'}}
    def args(self,*v):return app.parser().parse_args(v)
    def test_short_commands_parse(self):
        for argv in [('init',),('assess','--source','https://github.com/example/source.git'),('status',),('resume',),('approve','assessment'),
                     ('validate','--reviewer','claude-code'),('review-site','--provider','codex'),('approve','specifications'),('package',)]:
            self.args(*argv)
    def test_saved_workspace_is_private_and_resolved(self):
        guide.select_workspace(self.work)
        self.assertEqual(guide.workspace(),self.work.resolve())
        self.assertEqual(guide.active_file().stat().st_mode & 0o777,0o600)
    def test_missing_workspace_guides_to_init(self):
        with self.assertRaisesRegex(Blocked,'modernize init'):guide.workspace()
    def test_resume_never_creates_assessment(self):
        with self.assertRaisesRegex(Blocked,'No active'):guide.prepare_command(self.args('resume'),self.work,self.project)
        self.project['active_assessment']='run-1'
        args=self.args('resume');guide.prepare_command(args,self.work,self.project)
        self.assertEqual(args.label,'run-1')
    def test_new_run_number_and_active_pointer(self):
        args=self.args('assess','--allow-new-assessment')
        guide.prepare_command(args,self.work,self.project)
        self.assertEqual(args.label,'run-1')
        self.assertEqual(self.project['active_assessment'],'run-1')
        self.project['assessments']['run-1']={}
        args=self.args('assess','--allow-new-assessment');guide.prepare_command(args,self.work,self.project)
        self.assertEqual(args.label,'run-2')
    def test_changed_source_rejected_before_job(self):
        args=self.args('assess','--source','https://github.com/example/other')
        with self.assertRaisesRegex(Blocked,'Source differs'):guide.prepare_command(args,self.work,self.project)
    def test_approval_cannot_be_inferred_without_terminal(self):
        with patch.object(sys.stdin,'isatty',return_value=False):
            with self.assertRaisesRegex(Blocked,'requires --by'):guide.prepare_command(self.args('approve','assessment'),self.work,self.project)
    def test_interactive_approval_prompts_for_provenance(self):
        self.project['active_assessment']='run-1'
        with patch.object(sys.stdin,'isatty',return_value=True),patch('builtins.input',side_effect=['Fixture owner','Reviewed evidence','yes']):
            args=self.args('approve','assessment');guide.prepare_command(args,self.work,self.project)
        self.assertTrue(args.confirm_source_match)
        self.assertEqual(args.label,'run-1')
    def test_missing_tools_dont_mark_setup_ready(self):
        with patch.object(guide.shutil,'which',return_value=None):
            with self.assertRaisesRegex(Blocked,'Install missing'):guide.checks(self.project)
    def test_auth_diagnostics_not_disclosed(self):
        with patch.object(guide.shutil,'which',return_value='/fixture'),patch.object(guide,'command_ok',return_value=True),patch('sys.stdout',new_callable=io.StringIO) as output:
            guide.checks(self.project)
        self.assertNotIn('Account',output.getvalue())
    def test_guided_setup_resumes_existing_project_and_checks_environment(self):
        project=dict(self.project,setup={'connector_approved_by':'Fixture admin'})
        app.write(self.work/'project.json',project)
        with patch.object(sys.stdin,'isatty',return_value=True),patch('builtins.input',return_value=str(self.work)),patch.object(guide,'checks') as checks:
            result=guide.guided_init(self.args('init'))
        checks.assert_called_once()
        self.assertEqual(result['next_step'],'modernize assess')
    def test_new_wizard_saves_choices_and_exposes_incomplete_setup(self):
        project=dict(self.project,setup={},settings={'transform':{}})
        def initialize(args,work):
            self.assertEqual(args.source,'/fixture/source')
            self.assertEqual(args.bucket,'fixture-bucket')
            app.write(work/'project.json',project)
        answers=[str(self.work),'/fixture/source','Fixture scope','fixture','us-east-1','fixture-bucket','claude','codex','yes','no']
        with patch.object(sys.stdin,'isatty',return_value=True),patch('builtins.input',side_effect=answers),patch.object(app,'initialize',side_effect=initialize),patch.object(guide,'checks'),patch.object(guide,'ensure_aws_login'):
            result=guide.guided_init(self.args('init'))
        self.assertEqual(result['status'],'SETUP_INCOMPLETE')
        self.assertEqual(result['next_step'],'modernize init')
        self.assertEqual(guide.workspace(),self.work.resolve())

    def test_resume_routes_interrupted_model_work_without_aws_calls(self):
        project=dict(self.project,active_assessment='run-1',pending_action={'command':'validate'})
        app.write(self.work/'project.json',project)
        with patch.object(app,'pipeline',return_value={'status':'AWAITING_VALIDATION_APPROVAL'}) as pipeline,patch.object(app,'assessment',side_effect=AssertionError('No AWS resume')),patch('builtins.print'):
            result=app.main(['--workspace',str(self.work),'resume'])
        self.assertEqual(result,0)
        pipeline.assert_called_once()
        self.assertNotIn('pending_action',app.read(self.work/'project.json'))

    def test_ctrl_c_during_first_init_prompt_has_no_traceback(self):
        output=[]
        with patch.object(guide,'guided_init',side_effect=KeyboardInterrupt):
            code=app.main(['init','--guided'],reporter=output.append)
        self.assertEqual(code,130)
        self.assertEqual(output[0]['status'],'CANCELLED')
        self.assertEqual(output[0]['next_step'],'modernize init')
        self.assertFalse((self.work/'project.json').exists())

    def test_ctrl_c_retains_pending_phase_and_consumed_budget(self):
        app.write(self.work/'project.json',self.project)
        def interrupted(work,project,args):
            project['pipeline']={'calls':1}
            raise KeyboardInterrupt
        output=[]
        with patch.object(app,'pipeline',side_effect=interrupted):
            code=app.main(['--workspace',str(self.work),'validate'],reporter=output.append)
        saved=app.read(self.work/'project.json')
        self.assertEqual(code,130)
        self.assertEqual(saved['pipeline']['calls'],1)
        self.assertEqual(saved['pending_action']['command'],'validate')
        self.assertEqual(output[0]['status'],'CANCELLED')

    def test_valid_aws_session_does_not_launch_login(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(guide,'command_ok',return_value=True),patch.object(guide.subprocess,'run') as run:
            guide.ensure_aws_login(self.project)
        run.assert_not_called()

    def test_expired_sso_session_logs_in_and_rechecks_identity(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(sys.stdin,'isatty',return_value=True),patch.object(guide,'command_ok',side_effect=[False,True,True]) as verify,patch.object(guide,'yes',return_value=True),patch.object(guide.subprocess,'run',return_value=argparse.Namespace(returncode=0)) as run:
            guide.ensure_aws_login(self.project)
        command=run.call_args.args[0]
        self.assertEqual(command[-2:],['sso','login'])
        self.assertEqual(command[command.index('--profile')+1],'fixture')
        self.assertEqual(verify.call_args_list[-1].args[0][-2:],['sts','get-caller-identity'])

    def test_declined_login_stops_before_aws_login(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(sys.stdin,'isatty',return_value=True),patch.object(guide,'command_ok',side_effect=[False,True]),patch.object(guide,'yes',return_value=False),patch.object(guide.subprocess,'run') as run:
            with self.assertRaisesRegex(Blocked,'deferred'):guide.ensure_aws_login(self.project)
        run.assert_not_called()

    def test_login_success_without_identity_access_blocks(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(sys.stdin,'isatty',return_value=True),patch.object(guide,'command_ok',side_effect=[False,True,False]),patch.object(guide,'yes',return_value=True),patch.object(guide.subprocess,'run',return_value=argparse.Namespace(returncode=0)):
            with self.assertRaisesRegex(Blocked,'still unverified'):guide.ensure_aws_login(self.project)

    def test_scripted_login_never_prompts_or_opens_browser(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(sys.stdin,'isatty',return_value=False),patch.object(guide,'command_ok',return_value=False),patch.object(guide.subprocess,'run') as run:
            with self.assertRaisesRegex(Blocked,'authentication is required'):guide.ensure_aws_login(self.project)
        run.assert_not_called()

    def test_unconfigured_sso_requires_explicit_configuration_choice(self):
        with patch.object(guide.shutil,'which',return_value='/fixture/aws'),patch.object(sys.stdin,'isatty',return_value=True),patch.object(guide,'command_ok',side_effect=[False,False,False,True]),patch.object(guide,'yes',side_effect=[True,True]),patch.object(guide.subprocess,'run',return_value=argparse.Namespace(returncode=0)) as run:
            guide.ensure_aws_login(self.project)
        self.assertEqual(run.call_args_list[0].args[0][-2:],['configure','sso'])
        self.assertEqual(run.call_args_list[1].args[0][-2:],['sso','login'])

    def test_status_advertises_human_gate(self):
        self.project['stage']='AWAITING_ASSESSMENT_APPROVAL'
        self.assertIn('approve assessment',guide.next_step(self.project))

if __name__=='__main__':unittest.main()
