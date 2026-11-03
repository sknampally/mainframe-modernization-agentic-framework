"""Interactive onboarding and private active-workspace selection."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from pilot import require


def active_file():
    return Path.home() / '.config' / 'mainframe-modernize' / 'active.json'


def select_workspace(work):
    from kiro_workflow import private_save
    path = active_file()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    private_save(path, {'workspace': str(work)})


def workspace():
    path = active_file()
    require(path.is_file(), 'Run modernize init first, or select an existing --workspace')
    return Path(json.loads(path.read_text())['workspace']).expanduser().resolve()


def ask(label, default=None):
    value = input(label + (f' [{default}]' if default else '') + ': ').strip()
    result = value or default
    require(result, 'A value is required: ' + label)
    return result


def yes(label, default=False):
    answer = input(label + (' [Y/n]: ' if default else ' [y/N]: ')).strip().lower()
    require(answer in {'', 'y', 'yes', 'n', 'no'}, 'Answer yes or no')
    return answer in {'y', 'yes'} or (not answer and default)


def command_ok(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def installation_hint(tool):
    urls = {
        'git': 'https://git-scm.com/downloads',
        'aws': 'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html',
        'uv': 'https://docs.astral.sh/uv/getting-started/installation/',
        'uvx': 'https://docs.astral.sh/uv/getting-started/installation/',
        'claude': 'https://code.claude.com/docs/en/setup',
        'codex': 'https://learn.chatgpt.com/docs/codex/cli',
        'kiro-cli': 'https://kiro.dev/docs/cli/',
    }
    return tool + ': ' + urls.get(tool, 'Install your configured launcher through its approved vendor distribution')


def checks(project):
    """No model calls; authentication diagnostics are not printed or saved."""
    tools = ['git', 'aws', 'claude', 'codex' if project['providers']['wireframes'] == 'codex' else 'claude']
    tools.append(project.get('settings', {}).get('transform', {}).get('command', ['uvx'])[0])
    if project['providers']['executor'] == 'kiro': tools.append('kiro-cli')
    elif project['providers']['executor'] == 'codex': tools.append('codex')
    missing = sorted({tool for tool in tools if not shutil.which(tool)})
    require(not missing, 'Install missing tools, reopen your terminal, then rerun modernize init: ' + ', '.join(missing) + '\n' + '\n'.join(installation_hint(tool) for tool in missing) +
            '\nFull workstation guide: docs/engineer-setup.md in the framework checkout')
    require(command_ok(['claude', 'auth', 'status']), 'Run claude auth login, then rerun modernize init. See docs/engineer-setup.md for installation and authentication.')
    aws = ['aws']
    if project['aws'].get('profile'): aws += ['--profile', project['aws']['profile']]
    if project['aws'].get('region'): aws += ['--region', project['aws']['region']]
    require(command_ok(aws + ['sts', 'get-caller-identity']),
            'AWS login unavailable. Configure a new SSO profile with aws configure sso --profile <profile>, or sign in to the saved profile with aws sso login --profile <profile>. Then rerun modernize init. See docs/engineer-setup.md.')
    if project['providers']['executor'] == 'kiro':
        import os
        require(os.environ.get('KIRO_API_KEY'), 'Configure Kiro headless authentication, then rerun modernize init')
    if 'codex' in tools:
        require(command_ok(['codex', 'login', 'status']), 'Run codex login, then rerun modernize init')
    print('Required CLIs and saved AWS/Claude authentication checks passed.')


def guided_init(args):
    import modernize as app
    require(sys.stdin.isatty(), 'Interactive setup needs a terminal; supply --workspace, --source and --scope for scripted init')
    print('Modernization setup — source, environment, AWS assessment access and model roles.')
    print('Workstation installation and login instructions: ' + str(app.FRAMEWORK / 'docs/engineer-setup.md'))
    default = args.workspace
    if not default and active_file().exists(): default = str(workspace())
    work = Path(ask('Private workspace directory', default or str(Path.home() / 'modernization-poc' / 'carddemo'))).expanduser().resolve()
    require(not work.is_relative_to(app.FRAMEWORK), 'Choose a private workspace outside the framework checkout')
    args.workspace = str(work)
    if (work / 'project.json').exists():
        project = app.read(work / 'project.json')
        print('Resuming setup for the saved source and configuration; existing evidence will be preserved.')
    else:
        args.source = args.source or ask('Local Git checkout or GitHub repository URL', 'https://github.com/aws-samples/aws-mainframe-modernization-carddemo.git')
        if args.source.startswith('https://'):
            value = input('Git commit/ref to pin (Enter uses current default branch): ').strip()
            args.ref = args.ref or value or None
        args.scope = args.scope or ask('Business journey / assessment scope', 'CardDemo sign-on journey; exclude other application journeys')
        print('Use an existing AWS profile. If needed, configure it separately with aws configure sso.')
        args.aws_profile = args.aws_profile or ask('AWS profile', 'default')
        args.region = args.region or ask('AWS region', 'us-east-1')
        args.bucket = args.bucket or ask('Private S3 bucket name')
        args.executor = ask('Executor runtime: claude, kiro or codex', args.executor)
        require(args.executor in {'claude', 'kiro', 'codex'}, 'Unsupported executor runtime')
        args.ui_provider = ask('HTML content provider: claude or codex', args.ui_provider)
        require(args.ui_provider in {'claude', 'codex'}, 'Unsupported HTML provider')
        print('Claude defaults: Sonnet 5.5 executor / Opus 5.5 reviewer. Kiro is optional.')
        require(yes('Save these choices and pin the source?'), 'Setup cancelled before initialization')
        app.initialize(args, work)
        project = app.read(work / 'project.json')
    select_workspace(work)
    # From here all writes and remote setup share the regular project lock.
    with app.locked(work) as project:
        checks(project)
        for key, variable in (('profile', 'AWS_PROFILE'), ('region', 'AWS_DEFAULT_REGION')):
            if project['aws'].get(key): os.environ[variable] = project['aws'][key]
        if project.get('assessments') or project['setup'].get('connector_approved_by'):
            print('Existing assessment setup retained.')
            return {'workspace': str(work), 'status': project['stage'], 'next_step': next_step(project)}
        print('AWS Transform needs its own connection in addition to terminal AWS credentials.')
        print('Choose existing resources or authorize creation. No assessment job starts during init.')
        if not yes('Configure/check Transform resources now?'):
            return {'workspace': str(work), 'status': 'SETUP_INCOMPLETE', 'next_step': 'modernize init'}
        connect = input('Private MCP configure-arguments JSON file (Enter reuses existing connection): ').strip() or None
        config = project['settings']['transform']
        wid = config.get('workspace_id') or input('Existing Transform workspace ID (Enter creates one): ').strip()
        cid = project['setup'].get('connector_id') or input('Existing S3 connector ID (Enter creates one): ').strip()
        create_bucket = yes('Create the chosen bucket? Choose no to use an existing bucket.')
        setup = app.parser().parse_args(['setup'])
        setup.connect = connect
        setup.create_bucket = create_bucket
        setup.attach_workspace = wid or None
        setup.attach_connector = cid or None
        setup.create_workspace = None if wid else ask('New Transform workspace name', 'modernization-poc')
        setup.create_connector = None if cid else ask('New connector name', 'mainframe-source')
        require(yes('Proceed with these AWS setup operations?'), 'AWS setup cancelled; rerun modernize init to continue')
        try:
            result = app.setup(work, project, setup)
            if result.get('verification_link'): print('Connector approval: ' + result['verification_link'])
            if yes('Has an authorized administrator activated this connector?'):
                setup.create_bucket = False
                setup.connector_approved = ask('Name of approving administrator')
                result = app.setup(work, project, setup)
            return {'workspace': str(work), 'status': result['status'], 'next_step': next_step(project)}
        finally:
            app.persist(work, project)


def next_step(project):
    stage = project['stage']
    if project.get('pending_action'): return 'modernize resume'
    if stage == 'PACKAGED': return 'Inspect the generated package and its deferred work boundaries.'
    if stage == 'SPECIFICATIONS_APPROVED': return 'modernize package'
    if stage == 'AWAITING_SPECIFICATIONS_APPROVAL': return 'Review the HTML, then modernize approve specifications'
    if stage == 'VALIDATION_APPROVED': return 'modernize review-site'
    if stage == 'AWAITING_VALIDATION_APPROVAL': return 'Record SME decisions, then modernize approve validation'
    if stage in {'ASSESSMENT_APPROVED', 'REVISION_PENDING', 'WAITING_FOR_RUNTIME'}: return 'modernize validate --reviewer claude-code'
    if stage == 'AWAITING_ASSESSMENT_APPROVAL': return 'Inspect findings, then modernize approve assessment'
    if project.get('active_assessment') and project.get('assessments') and stage in {'INITIALIZED', 'READY_TO_ASSESS'}:
        return 'modernize status or modernize resume'
    if stage in {'INITIALIZED', 'WAITING_FOR_CONNECTOR_APPROVAL'}: return 'modernize init'
    return 'modernize assess' if not project['assessments'] else 'modernize status or modernize resume'


def prepare_command(args, work, project):
    """Resolve saved defaults; never interpret a missing resume label as a new run."""
    import modernize as app
    if args.command in {'assess', 'resume'}:
        if getattr(args, 'source', None):
            source = args.source
            matches = source.rstrip('/').removesuffix('.git') == project['source']['repository'].rstrip('/').removesuffix('.git')
            if not source.startswith('https://'): matches = str(Path(source).expanduser().resolve()) == project['source']['root']
            require(matches, 'Source differs from setup. Use modernize init with a new workspace to pin different source')
        if not args.label:
            if args.command == 'resume':
                require(project.get('active_assessment'), 'No active assessment to resume; use modernize assess')
                args.label = project['active_assessment']
            else:
                args.label = 'run-' + str(len(project['assessments']) + 1)
        if args.command == 'assess' and args.label not in project['assessments']:
            if not args.findings and not args.allow_new_assessment:
                require(sys.stdin.isatty(), 'New assessment needs --allow-new-assessment in noninteractive mode')
                print('Source: ' + project['source']['repository'] + ' @ ' + project['source'].get('commit', 'pinned revision'))
                print('Scope: ' + project.get('scope', 'saved scope'))
                print('Destination bucket: ' + str(project.get('aws', {}).get('bucket', 'saved bucket')))
                args.allow_new_assessment = yes('Upload this source and start a new AWS assessment?')
            project['active_assessment'] = args.label
            app.persist(work, project)
    if args.command == 'approve':
        args.label = args.label or project.get('active_assessment')
        if not args.by or not args.note:
            require(sys.stdin.isatty(), 'Noninteractive approval requires --by and --note')
            args.by = args.by or ask('Your name / accountable approval owner')
            args.note = args.note or ask('Approval rationale')
        if args.phase == 'assessment' and not args.confirm_source_match:
            require(sys.stdin.isatty(), 'Confirm assessment provenance with --confirm-source-match')
            args.confirm_source_match = yes('Have you inspected ingestion and confirmed findings match the pinned source and scope?')
