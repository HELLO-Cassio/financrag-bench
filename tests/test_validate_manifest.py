"""Synthetic fixtures exercise validation; no fixture is a real regulation."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_manifest import FIELDS, sha256_file, validate


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / 'manifest.csv'

    def row(self, number=1):
        key = f'DOC{number:02d}'
        source = self.root / 'data' / 'raw' / key / f'{key}_fixture_法律_现行.txt'
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f'Synthetic test fixture {number}', encoding='utf-8')
        row = dict.fromkeys(FIELDS, '')
        row.update(doc_id=key, title=f'Test only {number}', short_name=f'Test {number}',
                   issuer='Test issuer', doc_type='法律', authority_level='法律',
                   document_number=f'TEST-{number}', publish_date='2020-01-01',
                   effective_date='2020-02-01', status='current',
                   url=f'https://www.gov.cn/test-fixture/{number}.html',
                   fetched_at='2026-10-24', sha256=sha256_file(source),
                   local_path=source.relative_to(self.root).as_posix(),
                   scope_tag='核心', notes='Synthetic fixture, not legal data')
        return row

    def check(self, rows, mode='draft'):
        with self.manifest.open('w', encoding='utf-8-sig', newline='') as dest:
            writer = csv.DictWriter(dest, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        return validate(self.manifest, self.root, mode)

    def test_empty_draft_is_not_a_release(self):
        errors, warnings = self.check([])
        self.assertFalse(errors)
        self.assertTrue(warnings)
        self.assertTrue(self.check([], 'release')[0])

    def test_valid_bom_csv(self):
        self.assertEqual(self.check([self.row()])[0], [])

    def test_tampering_and_missing_file(self):
        row = self.row()
        path = self.root / row['local_path']
        path.write_text('tampered', encoding='utf-8')
        self.assertTrue(any('mismatch' in e for e in self.check([row])[0]))
        path.unlink()
        self.assertTrue(any('does not exist' in e for e in self.check([row])[0]))

    def test_fake_official_hostname(self):
        row = self.row()
        row['url'] = 'https://www.gov.cn.evil.example/file.html'
        self.assertTrue(any('domain' in e for e in self.check([row])[0]))

    def test_homepage_rejected(self):
        row = self.row()
        row['url'] = 'https://www.gov.cn/'
        self.assertTrue(any('homepage' in e for e in self.check([row])[0]))

    def test_path_escape(self):
        row = self.row()
        row['local_path'] = '../outside.txt'
        self.assertTrue(any('local_path' in e for e in self.check([row])[0]))

    def test_invalid_calendar_date(self):
        row = self.row()
        row['effective_date'] = '2025-02-30'
        self.assertTrue(any('effective_date' in e for e in self.check([row])[0]))

    def test_future_effective_current_rejected(self):
        row = self.row()
        row['effective_date'] = '2027-01-01'
        self.assertTrue(any('not effective' in e for e in self.check([row])[0]))

    def test_pending_only_allowed_in_draft(self):
        row = self.row()
        row['status'] = row['effective_date'] = '待核'
        self.assertFalse(self.check([row])[0])
        self.assertTrue(any('pending' in e for e in self.check([row], 'release')[0]))

    def test_duplicate_id_and_file(self):
        errors = self.check([self.row(), self.row()])[0]
        self.assertTrue(any('Duplicate doc_id' in e for e in errors))
        self.assertTrue(any('duplicate file' in e for e in errors))

    def test_missing_replacement_and_cycles(self):
        a, b = self.row(1), self.row(2)
        for row in (a, b):
            row.update(status='superseded', scope_tag='旧版', expiry_date='2021-01-01')
        self.assertTrue(any('requires replaced_by' in e for e in self.check([a])[0]))
        a['replaced_by'], b['replaced_by'] = 'DOC02', 'DOC01'
        self.assertTrue(any('cyclic' in e for e in self.check([a, b])[0]))

    def test_explanatory_material_has_no_legal_rank(self):
        row = self.row()
        row.update(scope_tag='解释', doc_type='解释材料', authority_level='不适用',
                   effective_date='', notes='解释材料，不作主证据')
        self.assertFalse(self.check([row])[0])
        row['authority_level'] = '法律'
        self.assertTrue(self.check([row])[0])

    def test_release_valid_fixture(self):
        rows = [self.row(i) for i in range(1, 66)]
        for row in rows[15:]:
            row['scope_tag'] = '配套'
        for row in rows[-5:]:
            row.update(scope_tag='旧版', status='superseded', expiry_date='2020-02-01',
                       effective_date='2018-02-01', publish_date='2018-01-01',
                       replaced_by='DOC01')
        self.assertFalse(self.check(rows, 'release')[0])

    def test_missing_columns_do_not_crash(self):
        self.manifest.write_text('doc_id,title\nDOC01,Test\n', encoding='utf-8')
        self.assertTrue(validate(self.manifest, self.root)[0])

    def test_malformed_row(self):
        self.manifest.write_text(','.join(FIELDS) + '\nDOC01,Test\n', encoding='utf-8')
        self.assertTrue(validate(self.manifest, self.root)[0])

    def test_cli_failure_exit_code(self):
        self.check([])
        script = Path(__file__).resolve().parents[1] / 'scripts' / 'validate_manifest.py'
        result = subprocess.run([sys.executable, str(script), str(self.manifest),
                                 '--mode', 'release'], capture_output=True)
        self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
