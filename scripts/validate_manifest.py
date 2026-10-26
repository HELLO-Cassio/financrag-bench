"""Validate E1 metadata and file integrity; legal review remains manual."""

import argparse
import csv
import hashlib
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

FIELDS = (
    'doc_id,title,short_name,issuer,doc_type,authority_level,document_number,'
    'publish_date,effective_date,expiry_date,status,replaced_by,url,fetched_at,'
    'sha256,local_path,scope_tag,notes'
).split(',')
TYPES = {'法律', '行政法规', '部门规章', '规范性文件', '自律规则', '标准'}
STATUSES = {'current', 'superseded', 'repealed', '待核'}
ROLES = {'核心', '配套', '旧版', '解释'}
DOC_ID = re.compile(r'DOC(?:0[1-9]|[1-9][0-9]+)\Z')
REPO_ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('expected YYYY-MM-DD')
    return date.fromisoformat(value)


def validate(manifest, root=REPO_ROOT, mode='draft', as_of=date(2026, 10, 23),
             official_domains=()):
    errors, warnings = [], []
    root = Path(root).resolve()
    try:
        with Path(manifest).open(encoding='utf-8-sig', newline='') as source:
            reader = csv.DictReader(source)
            if reader.fieldnames != FIELDS:
                return ['CSV header must contain the 18 documented fields in order.'], []
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        return [f'Cannot read manifest: {exc}'], []
    if any(None in row or any(v is None for v in row.values()) for row in rows):
        return ['Malformed CSV row: expected exactly 18 values. Quote commas/newlines.'], []
    rows = [{k: v.strip() for k, v in row.items()} for row in rows]
    if not rows:
        (errors if mode == 'release' else warnings).append(
            'No regulations collected. This is a scaffold, not an E1 release.')
    allowed = {'gov.cn', 'npc.gov.cn'} | {d.lower().strip('.') for d in official_domains}
    ids = [row['doc_id'] for row in rows]
    for key, count in Counter(ids).items():
        if count > 1:
            errors.append(f'Duplicate doc_id: {key}')
    by_id = {row['doc_id']: row for row in rows}
    seen_hashes, seen_versions = {}, set()

    for line, row in enumerate(rows, 2):
        key = row['doc_id'] or f'line {line}'

        def fail(message):
            errors.append(f'{key}: {message}')

        if not DOC_ID.fullmatch(row['doc_id']):
            fail('invalid doc_id (use DOC01, DOC02, ...).')
        for field in ('title', 'short_name', 'issuer', 'document_number', 'url',
                      'fetched_at', 'sha256', 'local_path', 'scope_tag', 'notes'):
            if not row[field]:
                fail(f'missing {field}')
        if row['status'] not in STATUSES:
            fail('invalid status')
        if row['scope_tag'] not in ROLES:
            fail('invalid scope_tag')
        interpretation = row['scope_tag'] == '解释'
        if interpretation:
            if row['doc_type'] != '解释材料' or row['authority_level'] != '不适用':
                fail('interpretations require doc_type=解释材料 and authority_level=不适用')
            if '不作主证据' not in row['notes']:
                fail('interpretation notes must state 不作主证据')
        elif row['doc_type'] not in TYPES or row['authority_level'] not in TYPES:
            fail('invalid doc_type/authority_level')

        pending = [f for f in ('document_number', 'publish_date', 'effective_date', 'status')
                   if row[f] == '待核']
        if pending:
            message = f'{key}: pending verification: {", ".join(pending)}'
            (errors if mode == 'release' else warnings).append(message)
        dates = {}
        for field in ('publish_date', 'effective_date', 'expiry_date', 'fetched_at'):
            value = row[field]
            required = field in {'publish_date', 'fetched_at'} or (
                field == 'effective_date' and not interpretation) or (
                field == 'expiry_date' and row['status'] in {'superseded', 'repealed'})
            if not value:
                if required:
                    fail(f'missing {field}; use 待核 for unresolved draft metadata')
                continue
            if value == '待核' and field != 'fetched_at' and mode == 'draft':
                continue
            try:
                dates[field] = parse_date(value)
            except ValueError:
                fail(f'invalid {field}: {value}')
        if dates.get('publish_date', date.min) > as_of:
            fail('publication is after the corpus snapshot date')
        if row['status'] == 'current':
            if row['expiry_date'] or row['replaced_by']:
                fail('current records must leave expiry_date/replaced_by empty')
            if dates.get('effective_date', date.min) > as_of:
                fail('current document was not effective at the snapshot date')
        if dates.get('expiry_date', date.max) < dates.get('effective_date', date.min):
            fail('expiry_date is before effective_date')
        if row['status'] in {'superseded', 'repealed'}:
            if row['scope_tag'] != '旧版':
                fail('historical documents must use scope_tag=旧版')
            if dates.get('expiry_date', date.min) > as_of:
                fail('historical document had not expired at the snapshot date')
        if row['scope_tag'] == '旧版' and row['status'] not in {'superseded', 'repealed', '待核'}:
            fail('旧版 role conflicts with status')
        if dates.get('fetched_at', date.max) < dates.get('publish_date', date.min):
            fail('fetched_at is before publication')

        try:
            url = urlsplit(row['url'])
            host = (url.hostname or '').lower()
            if url.scheme not in {'http', 'https'} or not host or url.username or url.password:
                fail('URL must be an official HTTP(S) URL without credentials')
            elif not any(host == d or host.endswith('.' + d) for d in allowed):
                fail('URL domain not approved; verify before adding --official-domain')
            if not url.path.strip('/') and not url.query:
                fail('URL is a homepage, not a document page')
        except ValueError:
            fail('invalid URL')

        relative = PurePosixPath(row['local_path'])
        folder = root / 'data' / 'raw' / row['doc_id']
        target = (root / Path(*relative.parts)).resolve()
        prefix = ('data', 'raw', row['doc_id'])
        if ('\\' in row['local_path'] or relative.is_absolute() or '..' in relative.parts
                or relative.parts[:3] != prefix or len(relative.parts) != 4
                or not relative.name.startswith(row['doc_id'] + '_')):
            fail('local_path must be data/raw/DOCxx/DOCxx_name_type_status.ext')
        elif not target.is_relative_to(root) or not target.is_relative_to(folder.resolve()):
            fail('file path escapes its document directory')
        elif not target.is_file():
            fail('local file does not exist')
        else:
            try:
                actual_hash = sha256_file(target)
                if target.stat().st_size == 0:
                    fail('local file is empty')
                if actual_hash != row['sha256'].lower():
                    fail('SHA256 mismatch')
                if actual_hash in seen_hashes:
                    fail(f'duplicate file content with {seen_hashes[actual_hash]}')
                seen_hashes[actual_hash] = key
            except OSError as exc:
                fail(f'cannot read local file: {exc}')
        if not re.fullmatch(r'[0-9a-fA-F]{64}', row['sha256']):
            fail('SHA256 must contain exactly 64 hexadecimal characters')
        version = (row['title'], row['document_number'], row['publish_date'])
        if version in seen_versions:
            fail('duplicate title/document_number/publication version')
        seen_versions.add(version)

        replacement = row['replaced_by']
        if row['status'] == 'superseded' and not replacement:
            fail('superseded record requires replaced_by')
        if replacement and (replacement not in by_id or replacement == row['doc_id']):
            fail('replaced_by must reference another manifest document')

    for start in by_id:
        visited, current = set(), start
        while current in by_id:
            if current in visited:
                errors.append(f'{start}: cyclic replaced_by chain')
                break
            visited.add(current)
            current = by_id[current]['replaced_by']

    if mode == 'release':
        roles = Counter(row['scope_tag'] for row in rows)
        if len(rows) != 65:
            errors.append('Release requires exactly 65 documents.')
        if roles['核心'] != 15:
            errors.append('Release requires exactly 15 core documents.')
        if sum(roles[r] for r in ('配套', '旧版', '解释')) != 50:
            errors.append('Release requires exactly 50 non-core documents (including old/explanatory).')
        if sum(row['status'] in {'superseded', 'repealed'} for row in rows) < 5:
            errors.append('Release requires at least 5 historical documents (one per member).')
        if not roles['解释']:
            warnings.append('No explanatory material; review the manual category coverage.')
    return errors, warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--mode', choices=['draft', 'release'], default='draft')
    parser.add_argument('--root', type=Path, default=REPO_ROOT)
    parser.add_argument('--as-of', type=parse_date, default=date(2026, 10, 23),
                        help='Snapshot date from docs/scope.md (default 2026-10-23)')
    parser.add_argument('--official-domain', action='append', default=[])
    args = parser.parse_args()
    errors, warnings = validate(args.manifest, args.root, args.mode, args.as_of,
                                args.official_domain)
    for message in warnings:
        print(f'WARN: {message}')
    for message in errors:
        print(f'ERROR: {message}')
    if errors:
        print(f'FAILED: {len(errors)} error(s)')
        return 1
    print(f'OK: {args.mode} metadata/file checks passed; manual review still required.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
