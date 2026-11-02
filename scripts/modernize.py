#!/usr/bin/env python3
"""Four-phase modernization preparation CLI. Never builds or deploys an application."""
import argparse
import contextlib
import difflib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import kiro_workflow as kw
from pilot import Blocked, git, require, sha
from modernize_artifacts import digest, validate_spec, validate_screens, render_site, SECTIONS
from modernize_models import call as model_call

FRAMEWORK = Path(__file__).resolve().parent.parent


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    kw.private_save(path, value)


def persist(work, project):
    write(work / 'project.json', project)


def name(value):
    require(bool(re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', value)), 'Use a short alphanumeric label with hyphens/underscores')
    return value


@contextlib.contextmanager
def locked(work):
    require((work / 'project.json').is_file(), 'Initialize this workspace first')
    with (work / '.project.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Blocked('Another command owns this workspace; try status or resume later') from error
        yield read(work / 'project.json')


def initialize(args, work):
    require(not (work / 'project.json').exists(), 'Workspace already initialized; use status')
    require(not work.is_relative_to(FRAMEWORK), 'Private workspace must be outside framework checkout')
    require(not git(FRAMEWORK, 'status', '--porcelain'), 'Use a clean committed framework checkout')
    work.mkdir(parents=True, exist_ok=True, mode=0o700)
    work.chmod(0o700)
    if args.source.startswith('https://'):
        require(bool(re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?', args.source)),
                'Remote source must be a GitHub HTTPS repository URL without credentials/query')
        source = work / 'source'
        require(not source.exists(), 'Clone destination already exists')
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--', args.source, str(source)],
                                capture_output=True, text=True, timeout=300)
        require(result.returncode == 0, 'Clone failed; authenticate Git separately and retry')
    else:
        source = Path(args.source).expanduser().resolve()
    require(source.is_dir() and not work.is_relative_to(source), 'Source must exist; workspace must be outside source')
    if args.ref:
        require(args.source.startswith('https://'), '--ref only applies to a new managed clone; pin local checkout yourself')
        result = subprocess.run(['git', '-C', str(source), 'checkout', '--detach', args.ref], capture_output=True, text=True)
        require(result.returncode == 0, 'Requested source ref could not be checked out')
    require(not git(source, 'status', '--porcelain'), 'Source checkout must be clean')
    config = kw.settings(args.settings)
    config['transform'].update({k: v for k, v in {'workspace_id': args.transform_workspace,
        'upload_prefix': ('s3://' + args.bucket + '/modernize') if args.bucket else None}.items() if v})
    project = {'version': 2, 'scope': args.scope, 'source': {'root': str(source),
        'repository': git(source, 'remote', 'get-url', 'origin'), 'commit': git(source, 'rev-parse', 'HEAD')},
        'framework_commit': git(FRAMEWORK, 'rev-parse', 'HEAD'), 'settings': config,
        'aws': {'profile': args.aws_profile, 'region': args.region, 'bucket': args.bucket},
        'providers': {'executor': args.executor, 'reviewer': 'claude', 'wireframes': args.ui_provider},
        'assessments': {}, 'approvals': {}, 'decisions': {}, 'setup': {}, 'events': [], 'stage': 'INITIALIZED'}
    persist(work, project)
    return {'workspace': str(work), 'status': project['stage'], 'source_commit': project['source']['commit']}


def aws(project, *args):
    command = ['aws']
    for key in ('profile', 'region'):
        if project['aws'].get(key):
            command += ['--' + key, project['aws'][key]]
    result = subprocess.run(command + list(args), capture_output=True, text=True, timeout=120)
    require(result.returncode == 0, 'AWS operation failed: ' + ' '.join(args[:2]) + '; check login, region and permissions')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def mutation(work, project, key, fn):
    """Record intent before remote creation; never retry an ambiguous side effect."""
    receipt = work / ('setup-' + key + '.json')
    if receipt.exists():
        project['setup'][key] = 'COMPLETE'
        return read(receipt)
    require(project['setup'].get(key) != 'PENDING',
            'Uncertain ' + key + ' creation; reconcile in AWS and use setup --attach-* rather than retry')
    project['setup'][key] = 'PENDING'
    persist(work, project)
    result = fn()
    write(receipt, result)
    project['setup'][key] = 'COMPLETE'
    persist(work, project)
    return result


def setup(work, project, args, client=None):
    identity = aws(project, 'sts', 'get-caller-identity', '--output', 'json')
    write(work / 'aws-identity.json', identity)
    config = project['settings']['transform']
    client = client or kw.Transform(config, work)
    if args.connect:
        # Exact supported configure payload is operator supplied privately; runtime schema is checked.
        client.calls([('configure', read(Path(args.connect)))])
    client.calls([('get_status', {})])
    if args.attach_workspace:
        require(not config.get('workspace_id') or config['workspace_id'] == args.attach_workspace, 'Workspace already selected')
        config['workspace_id'] = args.attach_workspace
        project['setup']['workspace'] = 'ATTACHED'
    if args.attach_connector:
        require(not project['setup'].get('connector_id') or project['setup']['connector_id'] == args.attach_connector, 'Connector already selected')
        project['setup']['connector_id'] = args.attach_connector
        project['setup']['connector'] = 'ATTACHED'
    bucket = project['aws']['bucket']
    require(bucket and project['aws']['region'], 'Set bucket and region at init for new assessments')
    if args.create_bucket:
        def create_bucket():
            command = ['s3api', 'create-bucket', '--bucket', bucket]
            if project['aws']['region'] != 'us-east-1':
                command += ['--create-bucket-configuration', json.dumps({'LocationConstraint': project['aws']['region']})]
            return aws(project, *command)
        mutation(work, project, 'bucket', create_bucket)
        aws(project, 's3api', 'put-public-access-block', '--bucket', bucket, '--public-access-block-configuration',
            'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true')
        aws(project, 's3api', 'put-bucket-encryption', '--bucket', bucket, '--server-side-encryption-configuration',
            json.dumps({'Rules': [{'ApplyServerSideEncryptionByDefault': {'SSEAlgorithm': 'AES256'}}]}))
    aws(project, 's3api', 'head-bucket', '--bucket', bucket, '--expected-bucket-owner', identity['Account'])
    public = aws(project, 's3api', 'get-public-access-block', '--bucket', bucket).get('PublicAccessBlockConfiguration', {})
    require(all(public.get(k) is True for k in ('BlockPublicAcls', 'IgnorePublicAcls', 'BlockPublicPolicy', 'RestrictPublicBuckets')),
            'Bucket must block public access; existing bucket policy is not modified automatically')
    if args.create_workspace and not config.get('workspace_id'):
        result = mutation(work, project, 'workspace', lambda: client.calls([('create_workspace',
            {'name': args.create_workspace, 'description': 'Mainframe assessment and preparation'})])[0])
        record = result.get('workspace', result)
        config['workspace_id'] = record.get('workspaceId') or record.get('id')
        require(config['workspace_id'], 'Workspace receipt has no identity; reconcile privately')
    require(config.get('workspace_id'), 'Supply --transform-workspace at init or --create-workspace/--attach-workspace at setup')
    if args.create_connector and not project['setup'].get('connector_id'):
        result = mutation(work, project, 'connector', lambda: client.calls([('create_connector', {
            'workspaceId': config['workspace_id'], 'connectorName': args.create_connector,
            'connectorType': 'S3', 'configuration': {'s3Uri': config['upload_prefix']},
            'awsAccountId': identity['Account']})])[0])
        require(result.get('connectorId'), 'Connector receipt has no identity; reconcile privately')
        project['setup']['connector_id'] = result['connectorId']
        project['setup']['verification_link'] = result.get('verificationLink')
    if args.role_arn:
        require(project['setup'].get('connector_id'), 'Create or attach a connector first')
        result = client.calls([('accept_connector', {'workspaceId': config['workspace_id'],
            'connectorId': project['setup']['connector_id'], 'roleArn': args.role_arn})])[0]
        write(work / 'connector-activation.json', result)
        # Activation response is retained, but operator must confirm readiness rather than guessing status fields.
    if args.connector_approved:
        require(project['setup'].get('connector_id'), 'No connector to confirm')
        project['setup']['connector_approved_by'] = args.connector_approved
    project['stage'] = 'READY_TO_ASSESS' if project['setup'].get('connector_approved_by') else 'WAITING_FOR_CONNECTOR_APPROVAL'
    persist(work, project)
    return {'status': project['stage'], 'verification_link': project['setup'].get('verification_link')}


def verify_source(project):
    kw.source_ok(project)


def assessment(work, project, args, client=None):
    label = name(args.label)
    if label not in project['assessments']:
        require(args.command == 'assess', 'Unknown assessment label; resume never creates a new run')
        verify_source(project)
        if not args.findings:
            require(args.allow_new_assessment, 'Use --allow-new-assessment to authorize this new job and source upload')
            require(project['setup'].get('connector_approved_by'), 'Complete setup and confirm connector activation first')
        settings_file = work / 'run-settings.json'
        write(settings_file, project['settings'])
        directory = kw.initialize(SimpleNamespace(source=project['source']['root'], workspace=str(work),
            settings=str(settings_file), objective=project['scope'], assessment=args.findings))
        project['assessments'][label] = {'directory': str(directory)}
        persist(work, project)
    directory = Path(project['assessments'][label]['directory'])
    run = read(directory / 'run.json')
    if args.findings and not run['assessment_ready']:
        run['assessment_input'] = args.findings
    if args.allow_new_assessment:
        run['settings']['allow_new_assessments'] = True
    try:
        verify_source(project)
        if args.attach_job:
            require(not run['job_id'] and run['create_pending'], 'Only reconcile an uncertain creation')
            service = client or kw.Transform(run['settings']['transform'], directory)
            record = service.calls([('get_job_status', {'workspaceId': run['settings']['transform']['workspace_id'],
                                    'jobId': args.attach_job, 'detailed': True})])[0]
            require(run['run_id'] in json.dumps(record), 'Attached job does not identify this run')
            run['job_id'], run['create_pending'] = args.attach_job, False
        polls = 0
        while not run['assessment_ready']:
            kw.assessment_step(run, directory, client)
            write(directory / 'run.json', run)
            polls += 1
            if not args.wait or run['status'] != 'WAITING_FOR_ASSESSMENT' or polls >= run['settings']['max_polls_per_resume']:
                break
            time.sleep(run['settings']['poll_seconds'])
        if run['assessment_ready']:
            run['status'] = 'AWAITING_ASSESSMENT_APPROVAL'
            project['assessments'][label]['sha256'] = digest(run['assessment_index'])
            project['stage'] = run['status'] if not project.get('selected') else project['stage']
    except Exception:
        run['status'] = 'NEEDS_RECONCILIATION' if run['create_pending'] and not run['job_id'] else 'BLOCKED'
        raise
    finally:
        write(directory / 'run.json', run)
        persist(work, project)
    return {'label': label, 'status': run['status'], 'reason': run.get('reason'), 'run': str(directory)}


def verified_assessment(project, label):
    record = project['assessments'][label]
    directory = Path(record['directory'])
    run = read(directory / 'run.json')
    require(run['assessment_ready'] and digest(run['assessment_index']) == record.get('sha256'), 'Assessment not sealed')
    for item in run['assessment_index']:
        path = directory / 'assessment' / item['path']
        require(path.is_file() and sha(path) == item['sha256'], 'Assessment content changed')
    return directory, run


def approved(project, phase, fingerprint):
    require(project['approvals'].get(phase, {}).get('sha256') == fingerprint, 'Missing or stale ' + phase + ' approval')


def spec_path(work, project):
    record = project['specification']
    path = work / record['path']
    require(sha(path) == record['sha256'], 'Specification changed after review')
    require(sha(work / record['review_path']) == record['review_sha256'], 'Independent review changed after acceptance')
    return path


def approve(work, project, args):
    verify_source(project)
    require(args.by.strip() and args.note.strip(), 'Named human owner and approval rationale required')
    if args.phase == 'assessment':
        require(args.label in project['assessments'], 'Select an assessment label')
        require(not project.get('pipeline'), 'Assessment already selected for validation; use a fresh workspace to change baseline')
        _, run = verified_assessment(project, args.label)
        require(args.confirm_source_match, 'Confirm findings match the pinned source/scope using --confirm-source-match')
        project['selected'] = args.label
        fingerprint = project['assessments'][args.label]['sha256']
        project['stage'] = 'ASSESSMENT_APPROVED'
    elif args.phase == 'validation':
        require(project.get('specification'), 'Complete independent validation first')
        require(not project.get('site'), 'Review site already generated; use feedback to revise')
        spec = read(spec_path(work, project))
        unresolved = [q['id'] for q in spec['questions'] if q['id'] not in project['decisions']]
        require(not unresolved, 'Record SME decisions first: ' + ', '.join(unresolved))
        fingerprint = digest({'specification': project['specification']['sha256'], 'decisions': project['decisions']})
        project['stage'] = 'VALIDATION_APPROVED'
    else:
        require(project.get('site'), 'Generate the review site first')
        fingerprint = site_fingerprint(work, project)
        approved(project, 'validation', digest({'specification': project['specification']['sha256'], 'decisions': project['decisions']}))
        project['stage'] = 'SPECIFICATIONS_APPROVED'
    project['approvals'][args.phase] = {'sha256': fingerprint, 'by': args.by, 'note': args.note, 'at': time.time()}
    persist(work, project)
    return {'status': project['stage'], 'approved_sha256': fingerprint}


def decision(work, project, args):
    spec = read(spec_path(work, project))
    require(args.question in {x['id'] for x in spec['questions']}, 'Unknown SME question')
    require(args.by.strip() and args.answer.strip(), 'Decision owner and answer required')
    project['decisions'][args.question] = {'by': args.by, 'answer': args.answer, 'disposition': args.disposition,
                                        'specification_sha256': project['specification']['sha256'], 'at': time.time()}
    project['approvals'].pop('validation', None)
    project['approvals'].pop('specifications', None)
    project.pop('site', None)
    project['stage'] = 'AWAITING_VALIDATION_APPROVAL'
    persist(work, project)
    return {'status': project['stage']}


def pipeline(work, project, args, runtime=model_call):
    verify_source(project)
    label = project.get('selected')
    require(label, 'Approve Phase 1 before running agents')
    assessment_dir, assessment_run = verified_assessment(project, label)
    approved(project, 'assessment', project['assessments'][label]['sha256'])
    state = project.setdefault('pipeline', {'round': 1, 'role': 'executor', 'calls': 0, 'contexts': {}, 'reads': {}, 'status': 'RUNNING'})
    require(state['status'] not in {'BLOCKED', 'REWORK_LIMIT'}, 'Resolve missing evidence via feedback before retrying')
    if project.get('specification'):
        return {'status': project['stage'], 'specification': project['specification']}
    area = work / 'preparation'
    area.mkdir(exist_ok=True, mode=0o700)
    while state['calls'] < project['settings']['max_model_calls']:
        role, number = state['role'], state['round']
        key = f'{number}:{role}'
        history = state['contexts'].setdefault(key, [])
        run = dict(assessment_run, settings=project['settings'], model_calls=state['calls'], round=number,
                   role_reads=state['reads'], events=[])
        context = {'protocol': (FRAMEWORK / 'prompts/pipeline' / (role + '.md')).read_text(),
            'scope': project['scope'], 'source': {k: v for k, v in project['source'].items() if k != 'root'},
            'source_files': kw.inventory(run), 'assessment_files': assessment_run['assessment_index'],
            'assessment_provenance': assessment_run.get('assessment_provenance'), 'history': history,
            'feedback': project.get('feedback', []), 'decisions': project['decisions']}
        if role == 'reviewer':
            candidate_path = area / f'candidate-{number}.json'
            require(sha(candidate_path) == state['candidate_sha256'], 'Candidate changed after handoff')
            context['candidate'] = read(candidate_path)
        if state.get('previous_review'):
            context['previous_review'] = state['previous_review']
        message = json.dumps(context)
        require(len(message.encode()) <= project['settings']['max_context_bytes'], 'Context limit reached; narrow the slice or adjust saved settings')
        state['calls'] += 1
        run['model_calls'] = state['calls']
        project['stage'] = 'RUNNING_' + role.upper()
        persist(work, project)
        reply = runtime(project['providers'][role], run, area, role, message)
        verify_source(project)
        write(area / f'reply-{state["calls"]}.json', reply)
        if reply.get('kind') == 'read':
            history.append({'request': reply, 'response': kw.source_read(run, assessment_dir, role, reply)})
            state['reads'] = run['role_reads']
        elif reply.get('kind') == 'blocked':
            state['status'], project['stage'] = 'BLOCKED', 'BLOCKED'
            state['reason'] = reply.get('reason', 'Evidence missing')
            break
        elif role == 'executor' and reply.get('kind') == 'candidate':
            require(state['reads'].get(key), 'Executor must inspect source')
            require(any(x['request'].get('area') == 'assessment' for x in history), 'Executor must inspect assessment findings')
            validate_spec(reply.get('specification'), Path(project['source']['root']))
            read_paths = {chunk['path'] for entry in history for chunk in entry['response'] if chunk['area'] == 'source'}
            require({rule['source_path'] for rule in reply['specification']['rules']} <= read_paths,
                    'Executor must inspect every rule source file')
            write(area / f'candidate-{number}.json', reply['specification'])
            state['candidate_sha256'] = sha(area / f'candidate-{number}.json')
            state['role'] = 'reviewer'
        elif role == 'reviewer' and reply.get('kind') == 'review':
            require(state['reads'].get(key), 'Reviewer must independently inspect source')
            require(any(x['request'].get('area') == 'assessment' for x in history), 'Reviewer must inspect assessment findings')
            require(reply.get('decision') in {'PASS', 'REWORK', 'BLOCKED'} and isinstance(reply.get('findings'), list)
                    and isinstance(reply.get('report'), str) and reply['report'].strip(), 'Invalid reviewer decision')
            write(area / f'review-{number}.json', reply)
            if reply['decision'] == 'PASS':
                read_paths = {chunk['path'] for entry in history for chunk in entry['response'] if chunk['area'] == 'source'}
                require({rule['source_path'] for rule in context['candidate']['rules']} <= read_paths,
                        'Reviewer must inspect every rule source file')
                require(not reply['findings'], 'PASS cannot have unresolved reviewer findings; SME questions remain separate')
                project['specification'] = {'path': f'preparation/candidate-{number}.json', 'sha256': state['candidate_sha256'],
                                            'review_sha256': sha(area / f'review-{number}.json'), 'review_path': f'preparation/review-{number}.json'}
                state['status'] = 'PASS'
                project['stage'] = 'AWAITING_VALIDATION_APPROVAL'
                break
            if reply['decision'] == 'BLOCKED' or number >= project['settings']['max_rounds']:
                state['status'] = 'BLOCKED' if reply['decision'] == 'BLOCKED' else 'REWORK_LIMIT'
                project['stage'] = state['status']
                break
            state.update(round=number + 1, role='executor', previous_review=reply)
        else:
            raise Blocked('Unsupported agent handshake')
        persist(work, project)
    else:
        state['status'], project['stage'] = 'BLOCKED', 'BLOCKED'
        state['reason'] = 'Total model call budget exhausted'
    persist(work, project)
    return {'status': project['stage'], 'calls': state['calls'], 'reason': state.get('reason')}


def site_fingerprint(work, project):
    site = project['site']
    for filename, expected in site['files'].items():
        require(sha(work / site['directory'] / filename) == expected, 'Review site changed; approval invalid')
    require(site['specification'] == project['specification']['sha256'] and site['decisions'] == digest(project['decisions']),
            'Review site belongs to stale specifications or decisions')
    return digest(site)


def review_site(work, project, args, runtime=model_call):
    verify_source(project)
    spec = read(spec_path(work, project))
    approved(project, 'validation', digest({'specification': project['specification']['sha256'], 'decisions': project['decisions']}))
    if project.get('site'):
        site_fingerprint(work, project)
        return {'status': project['stage'], 'html': str(work / project['site']['directory'] / 'index.html')}
    provider = args.provider or project['providers']['wireframes']
    require(provider in {'claude', 'codex'}, 'Review site provider must be claude or codex')
    project['ui_calls'] = project.get('ui_calls', 0) + 1
    require(project['ui_calls'] <= project['settings']['max_model_calls'], 'UI invocation budget exhausted')
    persist(work, project)
    directory = work / ('review-site-' + str(project['ui_calls']))
    directory.mkdir(mode=0o700)
    message = json.dumps({'protocol': (FRAMEWORK / 'prompts/pipeline/wireframes.md').read_text(),
                          'specification': spec, 'decisions': project['decisions']})
    require(len(message.encode()) <= project['settings']['max_context_bytes'], 'UI context exceeds budget')
    run = {'settings': project['settings'], 'model_calls': project['ui_calls']}
    screens = runtime(provider, run, directory, 'wireframes', message)
    verify_source(project)
    validate_screens(screens, spec)
    write(directory / 'screens.json', screens)
    (directory / 'index.html').write_text(render_site(spec, screens, project['decisions']))
    (directory / 'index.html').chmod(0o600)
    project['site'] = {'directory': directory.name, 'specification': project['specification']['sha256'],
                       'decisions': digest(project['decisions']), 'provider': provider,
                       'files': {p: sha(directory / p) for p in ('screens.json', 'index.html')}}
    project['stage'] = 'AWAITING_SPECIFICATIONS_APPROVAL'
    persist(work, project)
    return {'status': project['stage'], 'html': str(directory / 'index.html')}


def feedback(work, project, args):
    require(args.by.strip() and args.note.strip(), 'Feedback needs an owner and content')
    require(project.get('pipeline'), 'No preparation candidate to revise')
    state = project['pipeline']
    require(state['calls'] < project['settings']['max_model_calls'], 'Budget exhausted; start a new workspace with explicit limits')
    project.setdefault('feedback', []).append({'by': args.by, 'note': args.note, 'at': time.time()})
    require(state['round'] < project['settings']['max_rounds'], 'Revision limit exhausted; start a new workspace')
    state.update(round=state['round'] + 1, role='executor', status='RUNNING')
    for key in ('specification', 'site', 'package'):
        project.pop(key, None)
    project['decisions'] = {}
    project['approvals'].pop('validation', None)
    project['approvals'].pop('specifications', None)
    project['stage'] = 'REVISION_PENDING'
    persist(work, project)
    return {'status': project['stage']}


def package(work, project):
    verify_source(project)
    verified_assessment(project, project['selected'])
    spec = read(spec_path(work, project))
    approved(project, 'validation', digest({'specification': project['specification']['sha256'], 'decisions': project['decisions']}))
    approved(project, 'specifications', site_fingerprint(work, project))
    version = digest(project['approvals'])[:16]
    destination = work / ('package-' + version)
    require(not destination.exists(), 'Package already exists; inspect it or use feedback for a new version')
    destination.mkdir(mode=0o700)
    write(destination / 'specification.json', spec)
    write(destination / 'decisions.json', project['decisions'])
    write(destination / 'approvals.json', project['approvals'])
    write(destination / 'traceability.json', {'rules': spec['rules'], 'tests': spec['tests']})
    write(destination / 'implementation-backlog.json', spec['work_items'])
    (destination / 'monorepo-layout.txt').write_text('\n'.join(spec['monorepo_layout']) + '\n')
    for section in SECTIONS:
        (destination / (section + '-prompt.md')).write_text(
            '# Implementation task: ' + section + '\n\nUse the approved specification.json, decisions.json and traceability.json.\n'
            'Do not invent missing decisions or claim unexecuted tests passed. Respect deferred work boundaries.\n\n' +
            spec['sections'][section]['implementation_prompt'])
    shutil.copyfile(work / project['site']['directory'] / 'index.html', destination / 'review.html')
    write(destination / 'provenance.json', {'source': {k: v for k, v in project['source'].items() if k != 'root'},
        'scope': project['scope'], 'framework_commit': project['framework_commit'],
        'assessment_sha256': project['assessments'][project['selected']]['sha256'],
        'specification_sha256': project['specification']['sha256'],
        'limitations': ['No application built or deployed', 'No runtime equivalence established',
                        'Private package: review for confidential content before sharing'],
        'assistance': 'Specifications and wireframe content prepared with AI assistance; human approvals recorded separately'})
    (destination / 'README.md').write_text('# Implementation preparation package\n\n'
        'Start with review.html, specification.json and decisions.json. Work in backlog dependency order.\n'
        'Deferred decisions block the work identified in specification.json. This package is not a release approval.\n'
        'No application code or infrastructure has been deployed. All acceptance scenarios remain NOT RUN.\n'
        'Keep private; inspect all contents before sharing.\n')
    manifest = {p.name: sha(p) for p in destination.iterdir() if p.is_file()}
    write(destination / 'checksums.json', manifest)
    archive = work / (destination.name + '.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(destination.iterdir()):
            path.chmod(0o600)
            bundle.write(path, path.name)
    archive.chmod(0o600)
    project['package'] = {'path': archive.name, 'sha256': sha(archive)}
    project['stage'] = 'PACKAGED'
    persist(work, project)
    return {'status': 'PACKAGED', 'archive': str(archive), 'sha256': sha(archive)}


def compare(work, project, args):
    left_dir, left = verified_assessment(project, args.left)
    right_dir, right = verified_assessment(project, args.right)
    def normalized(directory, run):
        result = {}
        for item in run['assessment_index']:
            content = (directory / 'assessment' / item['path']).read_text()
            try:
                content = json.dumps(json.loads(content), sort_keys=True, indent=2)
            except ValueError:
                content = '\n'.join(line.rstrip() for line in content.splitlines()).strip()
            result[item['path']] = content
        return result
    a, b = normalized(left_dir, left), normalized(right_dir, right)
    paths = sorted(set(a) | set(b))
    differences = [{'path': p, 'status': 'ADDED' if p not in a else 'REMOVED' if p not in b else 'CHANGED',
                    'diff': '\n'.join(difflib.unified_diff(a.get(p, '').splitlines(), b.get(p, '').splitlines(),
                        fromfile=args.left + '/' + p, tofile=args.right + '/' + p))} for p in paths if a.get(p) != b.get(p)]
    controls = ['source', 'objective', 'settings', 'framework_commit']
    mismatches = [key for key in controls if left[key] != right[key]]
    report = {'left': args.left, 'right': args.right, 'recorded_configuration_matches': not mismatches,
              'mismatches': mismatches, 'differences': differences,
              'identical_files': len(paths) - len(differences), 'semantic_review': 'PENDING',
              'limitations': 'Content comparison only. JSON key order and trailing whitespace normalized. '
                  'Generated IDs, filenames and prose may still differ. No automatic judgment of correctness. '
                  'Service versions and human AWS responses are uncontrolled unless separately recorded.'}
    destination = work / ('comparison-' + name(args.left) + '-' + name(args.right) + '.json')
    write(destination, report)
    return {'report': str(destination), 'changed_files': len(differences), 'semantic_review': 'PENDING',
            'recorded_configuration_matches': not mismatches}



def semantic_compare(work, project, args, runtime=model_call):
    verify_source(project)
    left_dir, left = verified_assessment(project, args.left)
    right_dir, right = verified_assessment(project, args.right)
    state_path = work / ('comparison-' + name(args.left) + '-' + name(args.right) + '-state.json')
    baseline = digest([project['assessments'][args.left]['sha256'], project['assessments'][args.right]['sha256'], project['source']])
    state = read(state_path) if state_path.exists() else {'baseline': baseline, 'calls': 0, 'history': [], 'read_areas': []}
    require(state['baseline'] == baseline, 'Comparison baseline changed')
    output = work / ('comparison-' + args.left + '-' + args.right + '-semantic.json')
    if state.get('complete'):
        require(sha(output) == state['complete'], 'Semantic report changed')
        return {'report': str(output), 'semantic_review': 'AWAITING_HUMAN_REVIEW'}
    while state['calls'] < project['settings']['max_model_calls']:
        message = json.dumps({'protocol': (FRAMEWORK / 'prompts/pipeline/comparison.md').read_text(),
            'source_files': kw.inventory(left), 'left_files': left['assessment_index'], 'right_files': right['assessment_index'],
            'scope': project['scope'], 'history': state['history']})
        require(len(message.encode()) <= project['settings']['max_context_bytes'], 'Comparison context limit reached; no silent truncation')
        state['calls'] += 1
        write(state_path, state)
        run = dict(left, settings=project['settings'], model_calls=state['calls'])
        directory = work / ('compare-runtime-' + args.left + '-' + args.right)
        directory.mkdir(exist_ok=True, mode=0o700)
        reply = runtime(args.provider, run, directory, 'reviewer', message)
        verify_source(project)
        if reply.get('kind') == 'read':
            area = reply.get('area')
            require(area in {'left', 'right', 'source'}, 'Comparison read must select left, right or source')
            request = dict(reply, area='source' if area == 'source' else 'assessment')
            selected, selected_dir = (right, right_dir) if area == 'right' else (left, left_dir)
            chunks = kw.source_read(selected, selected_dir, 'reviewer', request)
            state['history'].append({'request': reply, 'response': chunks})
            state['read_areas'] = sorted(set(state['read_areas']) | {area})
        elif reply.get('kind') == 'candidate':
            require(set(state['read_areas']) == {'left', 'right', 'source'}, 'Comparison must inspect both findings and source')
            report = reply.get('comparison', {})
            require(all(isinstance(report.get(k), str) and report[k].strip() for k in ('summary', 'coverage_limitations'))
                    and isinstance(report.get('differences'), list), 'Comparison report incomplete')
            for difference in report['differences']:
                require(isinstance(difference, dict) and all(isinstance(difference.get(k), str) and difference[k].strip()
                    for k in ('category', 'description', 'impact', 'left_evidence', 'right_evidence', 'source_path', 'source_anchor', 'verdict')),
                    'Difference requires evidence and impact')
                require(difference['category'] in {'rules', 'dependencies', 'data', 'documentation', 'tests', 'coverage', 'other'}, 'Unknown comparison category')
                require(difference['verdict'] in {'LEFT_SUPPORTED', 'RIGHT_SUPPORTED', 'BOTH_SUPPORTED', 'NEITHER_SUPPORTED', 'SME_REQUIRED'}, 'Unknown verdict')
                kw.tracked_file(Path(project['source']['root']), difference['source_path'])
            report.update(baseline_sha256=baseline, semantic_review='AWAITING_HUMAN_REVIEW',
                          disclaimer='AI-assisted comparison; not an approval, executed test or general reliability estimate')
            write(output, report)
            state['complete'] = sha(output)
        else:
            raise Blocked(reply.get('reason', 'Unsupported comparison response'))
        write(state_path, state)
        if state.get('complete'):
            return {'report': str(output), 'semantic_review': 'AWAITING_HUMAN_REVIEW'}
    raise Blocked('Comparison invocation budget exhausted')


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True, help='Private workspace outside the framework and source checkout')
    commands = p.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Pin GitHub/local source and save private settings')
    init.add_argument('--source', required=True)
    init.add_argument('--ref')
    init.add_argument('--scope', required=True)
    init.add_argument('--settings')
    init.add_argument('--aws-profile')
    init.add_argument('--region')
    init.add_argument('--bucket')
    init.add_argument('--transform-workspace')
    init.add_argument('--executor', choices=['kiro', 'claude', 'codex'], default='kiro')
    init.add_argument('--ui-provider', choices=['claude', 'codex'], default='claude')
    s = commands.add_parser('setup', help='Check AWS, connect Transform, create or attach assessment resources')
    for flag in ('connect', 'create-workspace', 'create-connector', 'attach-workspace', 'attach-connector', 'role-arn', 'connector-approved'):
        s.add_argument('--' + flag)
    s.add_argument('--create-bucket', action='store_true')
    for command in ('assess', 'resume'):
        a = commands.add_parser(command)
        a.add_argument('--label', required=True)
        a.add_argument('--findings')
        a.add_argument('--allow-new-assessment', action='store_true')
        a.add_argument('--wait', action='store_true')
        a.add_argument('--detach', action='store_true')
        a.add_argument('--attach-job')
    commands.add_parser('status')
    a = commands.add_parser('approve')
    a.add_argument('phase', choices=['assessment', 'validation', 'specifications'])
    a.add_argument('--label')
    a.add_argument('--by', required=True)
    a.add_argument('--note', required=True)
    a.add_argument('--confirm-source-match', action='store_true')
    commands.add_parser('validate')
    d = commands.add_parser('decide')
    d.add_argument('--question', required=True)
    d.add_argument('--by', required=True)
    d.add_argument('--answer', required=True)
    d.add_argument('--disposition', choices=['resolved', 'deferred'], required=True)
    u = commands.add_parser('review-site')
    u.add_argument('--provider', choices=['claude', 'codex'])
    f = commands.add_parser('feedback')
    f.add_argument('--by', required=True)
    f.add_argument('--note', required=True)
    commands.add_parser('package')
    c = commands.add_parser('compare')
    c.add_argument('--left', required=True)
    c.add_argument('--right', required=True)
    c.add_argument('--semantic', action='store_true')
    c.add_argument('--provider', choices=['claude', 'codex'], default='claude')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    work = Path(args.workspace).expanduser().resolve()
    project = None
    try:
        if args.command == 'init':
            require(not work.is_relative_to(FRAMEWORK), 'Private workspace must be outside framework checkout')
            work.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (work / '.project.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as error:
                    raise Blocked('Another command is initializing this workspace') from error
                result = initialize(args, work)
        elif args.command == 'status':
            project = read(work / 'project.json')
            result = {'status': project['stage'], 'source_commit': project['source']['commit'],
                      'assessments': {k: read(Path(v['directory']) / 'run.json')['status'] for k, v in project['assessments'].items()},
                      'approvals': list(project['approvals']), 'package': project.get('package')}
        elif getattr(args, 'detach', False):
            require((work / 'project.json').is_file(), 'Initialize first')
            values = list(argv if argv is not None else sys.argv[1:])
            values.remove('--detach')
            if '--wait' not in values:
                values.append('--wait')
            with (work / 'controller.log').open('a') as log:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *values],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            result = {'status': 'LOCAL_WATCHER_STARTED', 'pid': process.pid, 'log': str(work / 'controller.log')}
        else:
            with locked(work) as project:
                # Make the reused assessment adapter use the same saved AWS profile/region.
                for key, variable in (('profile', 'AWS_PROFILE'), ('region', 'AWS_DEFAULT_REGION')):
                    if project['aws'].get(key):
                        os.environ[variable] = project['aws'][key]
                try:
                    if args.command == 'setup': result = setup(work, project, args)
                    elif args.command in {'assess', 'resume'}: result = assessment(work, project, args)
                    elif args.command == 'approve': result = approve(work, project, args)
                    elif args.command == 'validate': result = pipeline(work, project, args)
                    elif args.command == 'decide': result = decision(work, project, args)
                    elif args.command == 'review-site': result = review_site(work, project, args)
                    elif args.command == 'feedback': result = feedback(work, project, args)
                    elif args.command == 'package': result = package(work, project)
                    elif args.command == 'compare':
                        result = compare(work, project, args)
                        if args.semantic: result = semantic_compare(work, project, args)
                except kw.RuntimeUnavailable:
                    project['stage'] = 'WAITING_FOR_RUNTIME'
                    persist(work, project)
                    raise
                except Exception:
                    # Preserve consumed call counts and remote mutation markers on every failure.
                    persist(work, project)
                    raise
        print(json.dumps(result, indent=2))
        return 2 if result.get('status') in {'BLOCKED', 'REWORK_LIMIT', 'ASSESSMENT_FAILED', 'NEEDS_RECONCILIATION'} else 0
    except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
