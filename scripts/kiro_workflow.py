#!/usr/bin/env python3
"""Resumable Kiro two-role source-validation workflow. No live service is called by import."""
import argparse
import asyncio
import copy
import fcntl
import hashlib
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

from pilot import Blocked, git, require, save, sha, tracked_file

FRAMEWORK = Path(__file__).resolve().parent.parent
DEFAULTS = {
    'kiro_command': ['kiro-cli'], 'executor_model': None, 'reviewer_model': None, 'wireframes_model': None,
    'max_model_calls': 16, 'max_rounds': 2, 'call_timeout_seconds': 600,
    'max_context_bytes': 180000, 'max_read_bytes': 50000,
    'max_assessment_bytes': 10000000, 'max_source_upload_bytes': 100000000,
    'poll_seconds': 60, 'max_polls_per_resume': 120, 'allow_new_assessments': False, 'transform': {},
}
DENIED_NAMES = {'.env', 'credentials', 'config.json', 'id_rsa', 'id_ed25519'}
TEXT_SUFFIXES = {'.json', '.md', '.txt', '.csv', '.yaml', '.yml'}


def private_save(path, value):
    save(path, value)
    path.chmod(0o600)


def source_ok(run):
    root = Path(run['source']['root'])
    require(git(root, 'rev-parse', 'HEAD') == run['source']['commit'], 'Pinned source commit changed')
    require(not git(root, 'status', '--porcelain'), 'Source checkout is not clean')
    require(git(root, 'remote', 'get-url', 'origin') == run['source']['repository'], 'Source origin changed')
    require(git(FRAMEWORK, 'rev-parse', 'HEAD') == run['framework_commit'], 'Framework revision changed')
    require(not git(FRAMEWORK, 'status', '--porcelain'), 'Framework checkout is not clean')
    return root


def safe_name(name):
    p = Path(name)
    return (not p.is_absolute() and '..' not in p.parts and not any(x.startswith('.') for x in p.parts)
            and p.name not in DENIED_NAMES and p.suffix.lower() not in {'.pem', '.key', '.p12', '.pfx'})


def settings(path):
    config = copy.deepcopy(DEFAULTS)
    if path:
        supplied = json.loads(Path(path).read_text())
        require(isinstance(supplied, dict), 'Settings must be an object')
        require(not set(supplied) - set(DEFAULTS), 'Unknown settings keys')
        config.update(supplied)
    for name in ['max_model_calls', 'max_rounds', 'call_timeout_seconds', 'max_context_bytes',
                 'max_read_bytes', 'max_assessment_bytes', 'max_source_upload_bytes', 'poll_seconds', 'max_polls_per_resume']:
        require(type(config[name]) is int and config[name] > 0, 'Positive integer required: ' + name)
    require(config['poll_seconds'] >= 5, 'Poll interval must be at least five seconds')
    require(isinstance(config['kiro_command'], list) and config['kiro_command'] and
            all(isinstance(x, str) and x for x in config['kiro_command']), 'Kiro command must be an argv array')
    require(isinstance(config['transform'], dict), 'Transform settings must be an object')
    require(type(config['allow_new_assessments']) is bool, 'allow_new_assessments must be a boolean')
    return config


def initialize(args):
    source = Path(args.source).resolve()
    workspace = Path(args.workspace).resolve()
    require(source.is_dir() and workspace.is_dir(), 'Source and workspace must exist')
    require(not workspace.is_relative_to(source) and not workspace.is_relative_to(FRAMEWORK),
            'Run workspace must be outside source and framework checkouts')
    require(not git(source, 'status', '--porcelain'), 'Source checkout is not clean')
    require(not git(FRAMEWORK, 'status', '--porcelain'), 'Framework checkout is not clean')
    config = settings(args.settings)
    identity = 'RUN-' + uuid.uuid4().hex[:16]
    directory = workspace / 'runs' / identity
    directory.mkdir(parents=True, mode=0o700)
    run = {'version': 1, 'run_id': identity, 'framework_commit': git(FRAMEWORK, 'rev-parse', 'HEAD'),
           'source': {'root': str(source), 'repository': git(source, 'remote', 'get-url', 'origin'),
                      'commit': git(source, 'rev-parse', 'HEAD')},
           'objective': args.objective, 'assessment_input': args.assessment,
           'settings': config, 'config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
           'status': 'ASSESSMENT_PENDING', 'round': 1, 'role': 'executor', 'model_calls': 0,
           'role_reads': {}, 'contexts': {}, 'events': [], 'job_id': None,
           'create_pending': False, 'assessment_ready': False, 'reason': None}
    private_save(directory / 'run.json', run)
    return directory


def collect_assessment(run, directory, location):
    """Snapshot local/S3 text findings privately. Never extract arbitrary archives."""
    destination = directory / 'assessment'
    destination.mkdir(exist_ok=True, mode=0o700)
    limit = run['settings']['max_assessment_bytes']
    inventory = []
    if location.startswith('s3://'):
        from urllib.parse import urlparse
        parsed = urlparse(location)
        bucket, prefix = parsed.netloc, parsed.path.lstrip('/')
        require(bucket and prefix, 'S3 input must identify an object or nonempty prefix')
        def aws(*args):
            result = subprocess.run(['aws', *args], capture_output=True, text=True, timeout=120)
            require(result.returncode == 0, 'S3 operation failed; inspect AWS credentials/access privately')
            return json.loads(result.stdout) if result.stdout.strip() else {}
        if location.endswith('/'):
            objects = aws('s3api', 'list-objects-v2', '--bucket', bucket, '--prefix', prefix, '--output', 'json').get('Contents', [])
        else:
            metadata = aws('s3api', 'head-object', '--bucket', bucket, '--key', prefix, '--output', 'json')
            objects = [{'Key': prefix, 'Size': metadata['ContentLength']}]
        selected = []
        total = 0
        for obj in objects:
            relative = obj['Key'][len(prefix):] if location.endswith('/') else Path(prefix).name
            if not safe_name(relative) or Path(relative).suffix.lower() not in TEXT_SUFFIXES:
                continue
            total += obj['Size']
            selected.append((obj, relative))
        require(total <= limit, 'Assessment exceeds byte limit; choose a bounded prefix or adjust saved settings')
        for obj, name in selected:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            aws('s3api', 'get-object', '--bucket', bucket, '--key', obj['Key'], str(target))
    else:
        origin = Path(location).expanduser().resolve()
        require(origin.exists(), 'Assessment input does not exist')
        require(not destination.is_relative_to(origin), 'Assessment input must not contain this run directory')
        paths = [origin] if origin.is_file() else sorted(origin.rglob('*'))
        selected = []
        total = 0
        for path in paths:
            if not path.is_file() or path.is_symlink():
                continue
            name = path.name if origin.is_file() else path.relative_to(origin).as_posix()
            require(path.resolve().is_relative_to(origin if origin.is_dir() else origin.parent), 'Assessment path escapes origin')
            if safe_name(name) and path.suffix.lower() in TEXT_SUFFIXES:
                total += path.stat().st_size
                selected.append((path, name))
        require(total <= limit, 'Assessment exceeds byte limit; select a bounded folder or increase saved settings')
        for path, name in selected:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    for path in sorted(destination.rglob('*')):
        if path.is_file():
            path.chmod(0o600)
            inventory.append({'path': path.relative_to(destination).as_posix(), 'bytes': path.stat().st_size,
                              'sha256': sha(path)})
    require(inventory, 'No supported assessment text files found; JSON/Markdown/text/CSV/YAML are supported')
    private_save(directory / 'assessment-index.json', inventory)
    run['assessment_index'] = inventory
    run['assessment_ready'] = True
    run['assessment_provenance'] = {'location': location, 'baseline_match': 'UNVERIFIED; agents must inspect provenance'}


class RuntimeUnavailable(Blocked):
    pass


def mcp_transport(directory=None):
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        return ClientSession, StdioServerParameters, stdio_client
    except ImportError as error:
        if directory is not None:
            private_save(Path(directory) / 'mcp-error.json', {'type':type(error).__name__, 'detail':str(error),
                         'python_executable':sys.executable,'runtime_architecture':platform.machine()})
        blocked = Blocked('MCP dependency could not load; the package may be missing or use a different CPU architecture.')
        blocked.hint = 'From the framework checkout run: uv tool install --force --reinstall --managed-python --python 3.12 --editable .'
        raise blocked from error


class Transform:
    """Official AWS MCP SDK transport. Optional dependency imported only when used."""
    def __init__(self, config, directory):
        self.config, self.directory = config, directory

    def calls(self, requests):
        async def timed():
            return await asyncio.wait_for(self._calls(requests), timeout=self.config.get('timeout_seconds', 180))
        try:
            return asyncio.run(timed())
        except Blocked:
            raise
        except Exception as error:
            private_save(self.directory / 'mcp-error.json', {'type': type(error).__name__, 'detail': str(error)})
            raise Blocked('AWS MCP transport failed; inspect the private mcp-error.json and reconcile uncertain creation') from error

    async def _calls(self, requests):
        ClientSession, StdioServerParameters, stdio_client = mcp_transport(self.directory)
        command = self.config.get('command', ['uvx', 'awslabs.aws-transform-mcp-server@latest'])
        require(isinstance(command, list) and command, 'MCP command must be an argv array')
        env = dict(os.environ)
        env.update(self.config.get('env', {}))
        write_dir = self.directory / 'transform-artifacts'
        write_dir.mkdir(exist_ok=True, mode=0o700)
        env['AWS_TRANSFORM_MCP_WRITE_DIR'] = str(write_dir)
        parameters = StdioServerParameters(command=command[0], args=command[1:], env=env)
        responses = []
        log_path = self.directory / 'mcp-server.log'
        with log_path.open('a') as errlog:
            log_path.chmod(0o600)
            async with stdio_client(parameters, errlog=errlog) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    definitions = {tool.name: tool for tool in (await session.list_tools()).tools}
                    for name, arguments in requests:
                        require(name in definitions, 'Configured AWS tool unavailable: ' + name)
                        schema = getattr(definitions[name], 'input_schema', None) or getattr(definitions[name], 'inputSchema', {})
                        require(all(key in arguments for key in schema.get('required', [])), 'Required AWS tool arguments missing: ' + name)
                        require(not set(arguments) - set(schema.get('properties', {})), 'Unrecognized AWS arguments; do not guess')
                        result = await session.call_tool(name, arguments)
                        require(not getattr(result, 'is_error', getattr(result, 'isError', False)), 'AWS tool returned an error; inspect private receipts')
                        value = getattr(result, 'structured_content', None) or getattr(result, 'structuredContent', None)
                        if not value:
                            text = '\n'.join(block.text for block in result.content if getattr(block, 'type', '') == 'text')
                            value = json.loads(text)
                        responses.append(unwrap_mcp(value))
        return responses


def unwrap_mcp(value):
    for _ in range(8):
        require(isinstance(value, dict), 'Unsupported AWS tool response')
        require(not value.get('isError') and not value.get('error') and value.get('success') is not False,
                'AWS tool did not succeed; inspect authentication/configuration privately')
        if set(value) == {'result'}:
            value = value['result']
        elif 'content' in value and isinstance(value['content'], list):
            text = '\n'.join(x['text'] for x in value['content'] if x.get('type') == 'text')
            value = json.loads(text)
        elif value.get('success') is True and 'data' in value:
            value = value['data']
        else:
            return value
    raise Blocked('AWS response envelope nesting exceeded supported limit')


def export_findings(run, directory, client, identity):
    """Retrieve server-returned artifact IDs/assets; do not guess an export path."""
    target = directory / 'transform-artifacts'
    target.mkdir(exist_ok=True, mode=0o700)
    listing = client.calls([('load_instructions', identity),
                           ('list_resources', {**identity, 'resource': 'artifacts'})])[-1]
    private_save(directory / 'artifact-listing.json', listing)
    requests = []
    for item in listing.get('artifacts', []):
        if isinstance(item, dict) and item.get('artifactId'):
            requests.append({'resource': 'artifact', 'artifactId': item['artifactId']})
    for item in listing.get('assets', []):
        if isinstance(item, dict) and item.get('assetKey') and listing.get('connectorId'):
            if Path(item['assetKey']).suffix.lower() in TEXT_SUFFIXES:
                requests.append({'resource': 'asset', 'assetKey': item['assetKey'], 'connectorId': listing['connectorId']})
    require(len(requests) <= 40, 'More than 40 top-level artifacts; configure a bounded output_location in saved settings')
    require(requests, 'No downloadable top-level artifacts returned; configure output_location for nested/S3 exports')
    calls = [('load_instructions', identity)]
    for index, arguments in enumerate(requests):
        calls.append(('get_resource', {**identity, **arguments, 'savePath': str(target), 'fileName': f'finding-{index}.txt'}))
    client.calls(calls)
    # Reject binary/archives instead of pretending a service-status snapshot is the assessment.
    for path in target.glob('finding-*.txt'):
        raw = path.read_bytes()
        require(b'\0' not in raw, 'Binary artifact export requires an explicit text-output location')
        try:
            raw.decode('utf-8')
        except UnicodeDecodeError as error:
            raise Blocked('Non-UTF-8 artifact; configure a text-output location') from error
    collect_assessment(run, directory, str(target))
    run['assessment_provenance']['baseline_match'] = 'Job requested for this recorded source archive; ingestion and semantic content remain unverified'


def nested_job(value):
    for _ in range(5):
        if isinstance(value, dict) and ('jobId' in value or 'status' in value and 'job' not in value):
            return value
        if isinstance(value, dict) and 'job' in value:
            value = value['job']
        elif isinstance(value, dict) and 'data' in value:
            value = value['data']
        else:
            break
    raise Blocked('Job identity/status could not be established from the AWS response')


def assessment_step(run, directory, client=None):
    if run['assessment_ready']:
        return
    if run['assessment_input']:
        collect_assessment(run, directory, run['assessment_input'])
        run['status'] = 'AGENTS_PENDING'
        return
    config = run['settings']['transform']
    require(config.get('workspace_id'), 'Configure an existing AWS Transform workspace once in local settings')
    client = client or Transform(config, directory)
    if not run['job_id']:
        if run['create_pending'] and (directory / 'create-job-receipt.json').is_file():
            run['job_id'] = nested_job(json.loads((directory / 'create-job-receipt.json').read_text()))['jobId']
            run['create_pending'] = False
        if run['create_pending']:
            run['status'] = 'NEEDS_RECONCILIATION'
            run['reason'] = 'Job creation outcome uncertain. Reconcile and attach the existing job; never auto-create a duplicate.'
            return
        if run['job_id']:
            return assessment_step(run, directory, client)
        if not run['settings']['allow_new_assessments']:
            run['status'] = 'WAITING_FOR_AUTHORIZATION'
            run['reason'] = 'Authorize one new assessment at start/resume or enable the saved policy.'
            return
        require(config.get('upload_prefix', '').startswith('s3://'), 'New jobs require a configured private S3 upload prefix')
        client.calls([('get_status', {})])  # Establish transport before upload; service authorization may still fail.
        root = source_ok(run)
        archive = directory / 'source.zip'
        total = 0
        included, excluded = [], []
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for name in git(root, 'ls-files').splitlines():
                if not safe_name(name):
                    excluded.append(name)
                    continue
                path = tracked_file(root, name)
                total += path.stat().st_size
                require(total <= run['settings']['max_source_upload_bytes'], 'Source exceeds upload limit')
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100600 << 16
                content = path.read_bytes()
                bundle.writestr(info, content)
                included.append({'path': name, 'sha256': hashlib.sha256(content).hexdigest()})
        archive.chmod(0o600)
        private_save(directory / 'source-upload-manifest.json', {'included': included, 'excluded': excluded})
        source_uri = config['upload_prefix'].rstrip('/') + '/' + run['run_id'] + '/source.zip'
        result = subprocess.run(['aws', 's3', 'cp', str(archive), source_uri, '--only-show-errors'],
                                capture_output=True, text=True, timeout=120)
        require(result.returncode == 0, 'Source upload failed; no assessment job was requested')
        run['uploaded_source'] = {'uri': source_uri, 'sha256': sha(archive)}
        arguments = {'workspaceId': config['workspace_id'], 'jobName': run['run_id'],
                     'objective': 'Assess the source archive at ' + source_uri + '. Source commit ' + run['source']['commit'] +
                                  '. Scope: ' + run['objective'] +
                                  '. Produce discovery, documentation, rule candidates, data/dependency analysis and a draft test plan.',
                     'intent': config.get('intent', 'Assess this mainframe application; preserve required human review tasks.')}
        if config.get('orchestrator_agent'):
            arguments['orchestratorAgent'] = config['orchestrator_agent']
        run['create_pending'] = True
        run['status'] = 'CREATING_ASSESSMENT'
        private_save(directory / 'run.json', run)  # Persist before the non-idempotent MCP mutation.
        response = client.calls([('create_job', arguments)])[0]
        private_save(directory / 'create-job-receipt.json', response)
        run['job_id'] = nested_job(response)['jobId']
        run['create_pending'] = False
        private_save(directory / 'run.json', run)
    identity = {'workspaceId': config['workspace_id'], 'jobId': run['job_id']}
    responses = client.calls([('load_instructions', identity), ('get_job_status', {**identity, 'detailed': True})])
    snapshot = responses[-1]
    private_save(directory / 'assessment-status.json', snapshot)
    job = nested_job(snapshot)
    details = job.get('statusDetails', {})
    status = str(job.get('status') or (details.get('status') if isinstance(details, dict) else details) or 'UNKNOWN').upper()
    run['events'].append({'at': time.time(), 'event': 'assessment_status', 'status': status})
    if status in {'COMPLETED', 'SUCCEEDED'}:
        # Export paths vary by workflow. Ingest explicit configured output, never guess an artifact ID.
        output = config.get('output_location')
        if output:
            collect_assessment(run, directory, output.replace('{run_id}', run['run_id']).replace('{job_id}', run['job_id']))
        else:
            export_findings(run, directory, client, identity)
        run['status'] = 'AGENTS_PENDING'
    elif status in {'AWAITING_HUMAN_INPUT', 'PENDING_HUMAN_INPUT', 'AWAITING_APPROVAL'}:
        run['status'] = 'WAITING_FOR_HUMAN'
        run['reason'] = 'AWS Transform requires a human task decision. Complete it in the authorized UI, then resume this run.'
    elif status in {'FAILED', 'STOPPED', 'CANCELLED'}:
        run['status'] = 'ASSESSMENT_FAILED'
    else:
        run['status'] = 'WAITING_FOR_ASSESSMENT'
        run['reason'] = 'Job continues in AWS; resume or use --wait/--detach to monitor the same job.'


def json_reply(text):
    stripped = text.strip()
    if stripped.startswith('```json') and stripped.endswith('```'):
        stripped = stripped[7:-3].strip()
    value = json.loads(stripped)
    require(isinstance(value, dict) and value.get('kind') in {'read', 'candidate', 'review', 'blocked'},
            'Agent response is not a supported structured handshake')
    return value


def kiro_call(run, directory, role, message):
    config = run['settings']
    executable = config['kiro_command'][0]
    if not shutil.which(executable) or not os.environ.get('KIRO_API_KEY'):
        raise RuntimeUnavailable('Kiro headless setup requires kiro-cli and KIRO_API_KEY; configure them and resume')
    runtime = directory / 'runtime' / role
    agents = runtime / '.kiro' / 'agents'
    agents.mkdir(parents=True, exist_ok=True, mode=0o700)
    name = 'modernization-' + role
    profile = {'name': name, 'description': 'Controlled source-validation ' + role,
               'prompt': 'Follow the repository protocol supplied in the instruction. Return one JSON object only.',
               'tools': [], 'excludedTools': ['*'], 'mcpServers': {}, 'resources': [], 'hooks': [],
               'includeMcpJson': False, 'includePowers': False,
               'permissions': {'rules': [{'capability': 'all', 'effect': 'deny'}]}}
    model = config.get(role + '_model')
    if model:
        profile['model'] = model
    private_save(agents / (name + '.json'), profile)
    command = config['kiro_command'] + ['chat', '--v3', '--no-interactive', '--agent', name,
                                         '--trust-tools=', '--output-format', 'text']
    # No shell expansion, inherited working directory, --resume, or trust-all flag.
    process = subprocess.Popen(command, cwd=runtime, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(message, timeout=config['call_timeout_seconds'])
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
        private_save(directory / f'model-{run["model_calls"]}-timeout.json', {'stdout': stdout, 'stderr': stderr})
        raise RuntimeUnavailable('Kiro call exceeded its wall-clock limit and was terminated; resume within remaining call budget')
    private_save(directory / f'model-{run["model_calls"]}-receipt.json',
                 {'role': role, 'returncode': process.returncode, 'stdout': stdout, 'stderr': stderr})
    if process.returncode != 0:
        raise RuntimeUnavailable('Kiro failed or requires authentication; inspect the private model receipt and resume')
    return json_reply(stdout)


def inventory(run):
    root = source_ok(run)
    names = [name for name in git(root, 'ls-files').splitlines() if safe_name(name)]
    require(len(json.dumps(names).encode()) <= run['settings']['max_context_bytes'] // 2,
            'Source inventory exceeds context budget; configure a bounded source checkout')
    return names


def source_read(run, directory, role, request):
    paths = request.get('paths')
    require(isinstance(paths, list) and 0 < len(paths) <= 5 and all(isinstance(x, str) for x in paths),
            'Read request must name one to five paths')
    area = request.get('area', 'source')
    require(area in {'source', 'assessment'}, 'Read area must be source or assessment')
    root = source_ok(run) if area == 'source' else directory / 'assessment'
    chunks = []
    for name in paths:
        require(safe_name(name), 'Rejected path in agent read request')
        path = tracked_file(root, name) if area == 'source' else (root / name).resolve()
        require(path.is_relative_to(root.resolve()) and path.is_file() and not (root / name).is_symlink(), 'Read path escapes scope')
        if area == 'assessment':
            expected = next((x['sha256'] for x in run['assessment_index'] if x['path'] == name), None)
            require(expected == sha(path), 'Assessment snapshot changed')
        raw = path.read_bytes()
        require(len(raw) <= 10000000 and b'\0' not in raw, 'Requested file exceeds 10 MB or is binary')
        text = raw.decode('utf-8')
        start, end = request.get('start', 1), request.get('end', 300)
        require(type(start) is int and type(end) is int and 1 <= start <= end and end - start < 500,
                'Read ranges require positive start/end and at most 500 lines')
        selected = text.splitlines()[start-1:end]
        chunks.append({'area': area, 'path': name, 'sha256': sha(path),
                       'text': '\n'.join(f'{i}: {line}' for i, line in enumerate(selected, start))})
        require(len(chunks[-1]['text'].encode()) <= run['settings']['max_read_bytes'], 'Read result exceeds byte budget; request fewer lines')
    if area == 'source':
        run['role_reads'][f'{run["round"]}:{role}'] = run['role_reads'].get(f'{run["round"]}:{role}', 0) + len(chunks)
    run['events'].append({'event': 'read', 'role': role, 'round': run['round'],
                          'files': [{k: x[k] for k in ['area', 'path', 'sha256']} for x in chunks]})
    return chunks


def agent_step(run, directory, runtime=kiro_call):
    root = source_ok(run)
    role, number = run['role'], run['round']
    require(run['model_calls'] < run['settings']['max_model_calls'], 'Total model-call budget exhausted')
    if role == 'reviewer':
        require(sha(directory / f'candidate-{number}.json') == run['candidate_sha256'], 'Candidate changed after handoff')
    key = f'{number}:{role}'
    history = run['contexts'].setdefault(key, [])
    protocol = (FRAMEWORK / 'prompts' / 'automated' / (role + '.md')).read_text()
    context = {'protocol': protocol, 'task': {'objective': run['objective'], 'source': run['source'],
               'assessment_provenance': run.get('assessment_provenance'), 'round': number,
               'remaining_model_calls': run['settings']['max_model_calls'] - run['model_calls']},
               'source_files': inventory(run), 'assessment_files': run['assessment_index'], 'history': history}
    if role == 'reviewer':
        context['candidate'] = json.loads((directory / f'candidate-{number}.json').read_text())
    if number > 1:
        review_path = directory / f'review-{number-1}.json'
        require(sha(review_path) == run['review_sha256'][str(number-1)], 'Previous review changed')
        context['previous_review'] = json.loads(review_path.read_text())
    message = json.dumps(context)
    require(len(message.encode()) <= run['settings']['max_context_bytes'], 'Context budget exhausted; do not silently truncate evidence')
    run['model_calls'] += 1
    run['status'] = 'RUNNING_' + role.upper()
    run['inflight'] = {'role': role, 'round': number, 'call': run['model_calls']}
    private_save(directory / 'run.json', run)  # Budget persists even if the process dies.
    response = runtime(run, directory, role, message)
    source_ok(run)
    private_save(directory / f'reply-{run["model_calls"]}.json', response)
    run.pop('inflight', None)
    kind = response['kind']
    if kind == 'read':
        history.append({'request': response, 'response': source_read(run, directory, role, response)})
    elif kind == 'blocked':
        run['status'] = 'BLOCKED'
        run['reason'] = response.get('reason', 'Agent reports missing evidence')
    elif role == 'executor' and kind == 'candidate':
        require(run['role_reads'].get(key, 0) > 0, 'Executor did not inspect primary source')
        require(isinstance(response.get('specification'), str) and response['specification'].strip(), 'Candidate specification missing')
        rows = response.get('traceability')
        require(isinstance(rows, list) and len(rows) >= 3, 'Candidate needs positive/rejection/boundary scenario records')
        required = ['rule_id', 'source_path', 'source_anchor', 'scenario_id', 'expected_result', 'oracle', 'status']
        for row in rows:
            require(isinstance(row, dict) and all(isinstance(row.get(x), str) and row[x].strip() for x in required), 'Incomplete scenario')
            require(row['status'] == 'NOT RUN', 'Source-only workflow cannot claim executed tests')
            tracked_file(root, row['source_path'])
        private_save(directory / f'candidate-{number}.json', response)
        run['candidate_sha256'] = sha(directory / f'candidate-{number}.json')
        run['role'] = 'reviewer'
        run['status'] = 'REVIEW_PENDING'
    elif role == 'reviewer' and kind == 'review':
        require(run['role_reads'].get(key, 0) > 0, 'Reviewer did not independently inspect primary source')
        require(response.get('decision') in {'PASS', 'REWORK', 'BLOCKED'}, 'Unsupported review decision')
        require(isinstance(response.get('report'), str) and response['report'].strip(), 'Review report missing')
        require(isinstance(response.get('findings'), list), 'Review findings must be an array')
        if response['decision'] == 'PASS':
            require(not response['findings'], 'Automatic technical PASS requires no open findings; no human waiver is inferred')
        private_save(directory / f'review-{number}.json', response)
        run.setdefault('review_sha256', {})[str(number)] = sha(directory / f'review-{number}.json')
        if response['decision'] == 'PASS':
            run['status'] = 'AWAITING_HUMAN_ACCEPTANCE'
        elif response['decision'] == 'BLOCKED':
            run['status'] = 'BLOCKED'
            run['reason'] = response['report']
        elif number >= run['settings']['max_rounds']:
            run['status'] = 'REWORK_LIMIT'
        else:
            run['round'] += 1
            run['role'] = 'executor'
            run['status'] = 'EXECUTOR_PENDING'
    else:
        raise Blocked('Role returned an unsupported action; no output was accepted')
    run['events'].append({'event': kind, 'role': role, 'round': number, 'call': run['model_calls'], 'at': time.time()})


def summary(run, directory):
    return {'run': str(directory), 'run_id': run['run_id'], 'status': run['status'],
            'round': run['round'], 'model_calls': run['model_calls'], 'reason': run.get('reason'),
            'human_approved': False}


def drive(directory, wait=False, authorize=False, runtime=kiro_call, transform=None, assessment=None):
    directory = Path(directory).resolve()
    with (directory / '.workflow.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise Blocked('Another controller owns this run; use status rather than a second resume') from error
        run = json.loads((directory / 'run.json').read_text())
        if assessment:
            require(not run['assessment_ready'], 'Assessment already snapshotted; use a new run for different findings')
            run['assessment_input'] = assessment
            run['events'].append({'event': 'assessment_input_attached', 'at': time.time()})
        if authorize:
            run['settings']['allow_new_assessments'] = True
            run['events'].append({'event': 'new_assessment_authorized', 'at': time.time()})
        try:
            source_ok(run)
            if run.get('inflight'):
                # Model calls have no tool effects. A lost call may be retried within the remaining recorded budget.
                run['events'].append({'event': 'interrupted_model_call', 'receipt': run.pop('inflight')})
            polls = 0
            while True:
                if not run['assessment_ready']:
                    polls += 1
                    assessment_step(run, directory, transform)
                else:
                    terminal = {'AWAITING_HUMAN_ACCEPTANCE', 'BLOCKED', 'REWORK_LIMIT', 'ASSESSMENT_FAILED', 'NEEDS_RECONCILIATION'}
                    if run['status'] in terminal:
                        break
                    agent_step(run, directory, runtime)
                private_save(directory / 'run.json', run)
                if run['status'] == 'WAITING_FOR_ASSESSMENT' and wait:
                    if polls >= run['settings']['max_polls_per_resume']:
                        run['reason'] = 'Watcher poll limit reached; AWS job continues. Resume later with the same run.'
                        break
                    time.sleep(run['settings']['poll_seconds'])
                    continue
                if run['status'] in {'WAITING_FOR_ASSESSMENT', 'WAITING_FOR_HUMAN', 'WAITING_FOR_AUTHORIZATION',
                                     'ASSESSMENT_FAILED', 'NEEDS_RECONCILIATION', 'BLOCKED', 'REWORK_LIMIT', 'AWAITING_HUMAN_ACCEPTANCE'}:
                    break
        except RuntimeUnavailable as error:
            run['status'], run['reason'] = 'WAITING_FOR_RUNTIME', str(error)
        except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
            run['status'] = 'NEEDS_RECONCILIATION' if run['create_pending'] and not run['job_id'] else 'BLOCKED'
            run['reason'] = str(error)
        finally:
            private_save(directory / 'run.json', run)
        return summary(run, directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('start')
    for name in ['source', 'workspace']:
        start.add_argument('--' + name, required=True)
    start.add_argument('--settings')
    start.add_argument('--assessment', help='Existing local text findings or S3 object/prefix; omit for new assessment')
    start.add_argument('--objective', default='Validate one bounded business rule against source and assessment; produce explicit oracles and gaps.')
    start.add_argument('--allow-new-assessment', action='store_true')
    start.add_argument('--wait', action='store_true')
    start.add_argument('--detach', action='store_true')
    for name in ['resume', 'status', 'attach-job']:
        command = commands.add_parser(name)
        command.add_argument('--run', required=True)
        if name == 'resume':
            command.add_argument('--wait', action='store_true')
            command.add_argument('--allow-new-assessment', action='store_true')
            command.add_argument('--detach', action='store_true')
            command.add_argument('--assessment', help='Attach existing findings if automatic export needs an explicit location')
        if name == 'attach-job':
            command.add_argument('--job-id', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'start':
            # Fail preflight before uploading source or making a new AWS job.
            config = settings(args.settings)
            require(shutil.which(config['kiro_command'][0]), 'Install kiro-cli before starting an automated run')
            require(os.environ.get('KIRO_API_KEY'), 'Configure KIRO_API_KEY for Kiro headless mode')
            directory = initialize(args)
        else:
            directory = Path(args.run).resolve()
        if args.command == 'status':
            print(json.dumps(summary(json.loads((directory / 'run.json').read_text()), directory), indent=2))
            return 0
        if args.command == 'attach-job':
            with (directory / '.workflow.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                run = json.loads((directory / 'run.json').read_text())
                require(run['status'] == 'NEEDS_RECONCILIATION' and not run['job_id'], 'Attach is only for uncertain job creation')
                cfg = run['settings']['transform']
                responses = Transform(cfg, directory).calls([('load_instructions', {'workspaceId': cfg['workspace_id'], 'jobId': args.job_id}),
                    ('get_job_status', {'workspaceId': cfg['workspace_id'], 'jobId': args.job_id, 'detailed': True})])
                job = nested_job(responses[-1])
                require(run['run_id'] in json.dumps(job), 'Job does not reference this run; refusing to attach')
                run['job_id'], run['create_pending'], run['status'] = args.job_id, False, 'WAITING_FOR_ASSESSMENT'
                private_save(directory / 'run.json', run)
                print(json.dumps(summary(run, directory), indent=2))
                return 0
        if args.detach:
            command = [sys.executable, str(Path(__file__).resolve()), 'resume', '--run', str(directory), '--wait']
            if args.allow_new_assessment:
                command.append('--allow-new-assessment')
            if args.command == 'resume' and args.assessment:
                command += ['--assessment', args.assessment]
            with (directory / 'controller.log').open('ab') as output:
                process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=output, stderr=output, start_new_session=True)
            print(json.dumps({'run': str(directory), 'pid': process.pid, 'status': 'CONTROLLER_STARTED',
                              'note': 'Local process, not a cloud service; use resume after shutdown.'}, indent=2))
        else:
            result = drive(directory, args.wait, args.allow_new_assessment,
                           assessment=args.assessment if args.command == 'resume' else None)
            print(json.dumps(result, indent=2))
            return 2 if result['status'] in {'BLOCKED', 'ASSESSMENT_FAILED', 'NEEDS_RECONCILIATION', 'REWORK_LIMIT'} else 0
    except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'BLOCKED', 'reason': str(error)}))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
