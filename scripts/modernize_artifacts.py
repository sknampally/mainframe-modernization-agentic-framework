"""Structured specification validation and inert, portable HTML rendering."""
import hashlib
import html
import json
from pathlib import Path
from pilot import require, tracked_file

SECTIONS = ('architecture', 'ui', 'services', 'data', 'infrastructure', 'security',
            'migration', 'testing', 'operations', 'delivery')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value):
    return isinstance(value, list) and all(text(x) for x in value)


def validate_spec(spec, source):
    require(isinstance(spec, dict), 'Specification must be an object')
    require(text(spec.get('scope')) and text(spec.get('excluded_scope')), 'Explicit scope and exclusions required')
    rules = spec.get('rules')
    require(isinstance(rules, list) and rules, 'At least one source-traceable rule required')
    ids = set()
    for rule in rules:
        require(isinstance(rule, dict) and all(text(rule.get(k)) for k in
                ('id', 'statement', 'source_path', 'source_anchor', 'evidence_status')), 'Incomplete rule')
        require(rule['id'] not in ids, 'Duplicate rule ID')
        ids.add(rule['id'])
        require(rule['evidence_status'] in {'SOURCE_VERIFIED', 'INFERRED', 'UNKNOWN'}, 'Invalid evidence status')
        tracked_file(source, rule['source_path'])
    require(isinstance(spec.get('sections'), dict) and set(spec['sections']) == set(SECTIONS),
            'All preparation sections required; use explicit not-applicable explanations')
    for section in spec['sections'].values():
        require(isinstance(section, dict) and text(section.get('specification')) and text(section.get('implementation_prompt')),
                'Each section needs a specification and reusable implementation prompt')
        require(strings(section.get('rule_ids')) and set(section['rule_ids']) <= ids, 'Unknown section rule reference')
    require(isinstance(spec.get('questions'), list), 'SME questions list required')
    qids = set()
    for question in spec['questions']:
        require(isinstance(question, dict) and all(text(question.get(k)) for k in
                ('id', 'question', 'impact', 'owner', 'blocks')), 'SME question needs owner, impact and blocked work')
        require(question['id'] not in qids, 'Duplicate question ID')
        qids.add(question['id'])
    require(all(r['evidence_status'] == 'SOURCE_VERIFIED' for r in rules) or spec['questions'],
            'Inferred/unknown rules require explicit SME questions')
    require(isinstance(spec.get('tests'), list) and len(spec['tests']) >= 3, 'Normal, rejection and boundary scenarios required')
    require({x.get('category') for x in spec['tests'] if isinstance(x, dict)} == {'normal', 'rejection', 'boundary'},
            'Tests must cover normal, rejection and boundary categories')
    test_ids = set()
    covered = set()
    for case in spec['tests']:
        require(isinstance(case, dict) and all(text(case.get(k)) for k in ('id', 'rule_id', 'given', 'when', 'then', 'oracle')),
                'Incomplete test specification')
        require(case['rule_id'] in ids and case.get('status') == 'NOT RUN', 'Tests must reference known rules and remain NOT RUN')
        require(case['id'] not in test_ids, 'Duplicate test ID')
        test_ids.add(case['id'])
        covered.add(case['rule_id'])
    require(covered == ids, 'Every rule needs an acceptance scenario')
    require(isinstance(spec.get('work_items'), list) and spec['work_items'], 'Ordered implementation work items required')
    seen = set()
    for item in spec['work_items']:
        require(isinstance(item, dict) and all(text(item.get(k)) for k in ('id', 'title', 'acceptance')),
                'Incomplete work item')
        require(item['id'] not in seen and strings(item.get('depends_on')) and set(item['depends_on']) <= seen,
                'Work items must have unique IDs in dependency order')
        seen.add(item['id'])
    require(strings(spec.get('monorepo_layout')) and spec['monorepo_layout'], 'Proposed monorepo layout required')


def validate_screens(value, spec):
    require(isinstance(value, dict) and isinstance(value.get('screens'), list) and value['screens'], 'Screens required')
    rules = {r['id'] for r in spec['rules']}
    require(isinstance(value.get('apis'), list), 'Structured API contracts required; use an empty list only when no APIs are proposed')
    operations = set()
    for api in value['apis']:
        require(isinstance(api, dict) and all(text(api.get(key)) for key in
                ('id','method','path','purpose','authentication','uncertainties')), 'Incomplete API contract')
        require(api['method'] in {'GET','POST','PUT','PATCH','DELETE'} and api['path'].startswith('/')
                and not api['path'].startswith('//'), 'API requires a relative route and supported method')
        key = (api['method'],api['path'])
        require(key not in operations, 'Duplicate API operation')
        operations.add(key)
        require(isinstance(api.get('request'), dict) and isinstance(api.get('responses'), dict)
                and api['responses'], 'API request and response contracts required')
        require(strings(api.get('rule_ids')) and set(api['rule_ids']) <= rules, 'Unknown API rule reference')
    ids = set()
    for screen in value['screens']:
        require(isinstance(screen, dict) and all(text(screen.get(k)) for k in ('id', 'title', 'purpose', 'uncertainties')),
                'Screen requires ID, purpose and explicit uncertainties')
        require(screen['id'] not in ids, 'Duplicate screen ID')
        ids.add(screen['id'])
        require(strings(screen.get('rule_ids')) and set(screen['rule_ids']) <= rules, 'Screen has unknown rule reference')
        require(strings(screen.get('fields')) and strings(screen.get('actions')) and strings(screen.get('states')),
                'Screen fields, actions and states must be text arrays')
        require(screen['states'], 'Screen must explain normal, error and boundary states')


def render_site(spec, screens, decisions, title='Modernization review'):
    """Never execute model-generated HTML, JavaScript, URLs or styles."""
    esc = lambda x: html.escape(str(x), quote=True)
    blocks = []
    if screens['screens']:
        blocks.append('<nav aria-label="Prototype screens"><h2>Application walkthrough</h2><ul>' +
                      ''.join('<li><a href="#screen-' + str(index) + '">' + esc(screen['title']) + '</a></li>'
                              for index, screen in enumerate(screens['screens'])) + '</ul></nav>')
    blocks.append('<h2>Scope</h2><p>' + esc(spec['scope']) + '</p><h3>Excluded</h3><p>' + esc(spec['excluded_scope']) + '</p>')
    for index, screen in enumerate(screens['screens']):
        fields = ''.join('<label>' + esc(f) + '<input disabled placeholder="Illustrative only"></label>' for f in screen['fields'])
        actions = ''.join('<button disabled>' + esc(a) + '</button>' for a in screen['actions'])
        blocks.append('<article id="screen-' + str(index) + '"><h2>' + esc(screen['title']) + '</h2><p>' + esc(screen['purpose']) + '</p>' + fields + actions +
                      '<p>Rules: ' + esc(', '.join(screen['rule_ids'])) + '</p><h3>States</h3><p>' + esc('; '.join(screen['states'])) +
                      '</p><h3>Uncertainties</h3><p>' + esc(screen['uncertainties']) + '</p></article>')
    blocks.append('<h2>Business rules</h2>')
    if screens.get('apis'):
        blocks.append('<h2>Proposed API contracts</h2><pre>' + esc(json.dumps(screens['apis'], indent=2)) + '</pre>')
    for r in spec['rules']:
        blocks.append('<article><h3>' + esc(r['id']) + ' · ' + esc(r['evidence_status']) + '</h3><p>' + esc(r['statement']) +
                      '</p><p>Evidence: ' + esc(r['source_path'] + ' ' + r['source_anchor']) + '</p></article>')
    for name in SECTIONS:
        blocks.append('<details><summary>' + esc(name.title()) + '</summary><pre>' + esc(spec['sections'][name]['specification']) + '</pre></details>')
    blocks.append('<h2>SME decisions</h2><pre>' + esc(json.dumps({'questions': spec['questions'], 'decisions': decisions}, indent=2)) + '</pre>')
    blocks.append('<h2>Acceptance scenarios — NOT RUN</h2><pre>' + esc(json.dumps(spec['tests'], indent=2)) + '</pre>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'">
<title>''' + esc(title) + '''</title><style>body{font:16px/1.6 system-ui;margin:0;background:#eef2f7;color:#172b46}main{max-width:1000px;margin:auto;padding:36px}article,details{background:white;border:1px solid #c9d4e2;border-radius:12px;padding:24px;margin:18px 0}h1{font-size:34px}h2{color:#153f72}label{display:block;margin:12px 0}input{display:block;padding:10px;width:90%;max-width:420px}button{padding:10px 20px;margin:8px;background:#dae5f3;border:1px solid #7185a0;border-radius:6px;color:#334}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer;font-weight:700}.notice{padding:16px;background:#fff2cf;border-left:4px solid #8b6500}</style><main><h1>''' + esc(title) + '''</h1><p class="notice">Review prototype only. No backend, no executed equivalence tests, and no production deployment. Approval is recorded separately against this exact version.</p>''' + ''.join(blocks) + '</main></html>'
