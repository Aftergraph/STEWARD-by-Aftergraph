from pathlib import Path
import json, sys
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
required = [
    'README.md', '.steward.md', 'AGENTS.md',
    'docs/00-MASTER-ARCHITECTURE.md', 'docs/02-DEFINITIONS.md',
    'docs/03-COMPONENT-OWNERSHIP.md', 'docs/14-IMPLEMENTATION-PLAN.md',
    'schemas/intent-envelope.schema.json', 'schemas/work-claim.schema.json',
    'schemas/habitat-spec.schema.json', 'schemas/git-execution-context.schema.json',
    'schemas/git-effect-intent.schema.json', 'schemas/verification-verdict.schema.json'
]
errors = []
for rel in required:
    if not (ROOT / rel).exists():
        errors.append(f'missing required file: {rel}')

schema_ids = set()
for path in sorted((ROOT / 'schemas').glob('*.json')):
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(data)
        if '$id' not in data or '$schema' not in data:
            errors.append(f'schema metadata missing: {path.name}')
        elif data['$id'] in schema_ids:
            errors.append(f'duplicate schema id: {data["$id"]}')
        else:
            schema_ids.add(data['$id'])
    except Exception as exc:
        errors.append(f'invalid schema {path.name}: {exc}')

if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'STEWARD_SPEC_VALIDATE=PASS schemas={len(schema_ids)}')
