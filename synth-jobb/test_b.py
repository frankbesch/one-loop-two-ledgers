#!/usr/bin/env python3
"""Non-rendering gate regression tests; fixtures and scratch stay in this folder."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import check_b


class GateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gate-test-', dir=check_b.ROOT)
        self.root = Path(self.temp.name)
        for name in ['case_spec_b.json', 'truth_b.json', 'manifest_b.json', 'rekey_fields_b.md', 'quotas-b.md']:
            shutil.copyfile(check_b.ROOT/name, self.root/name)
        for name in ['sources', 'reference']:
            shutil.copytree(check_b.ROOT/name, self.root/name)
        (self.root/'clean').mkdir()
        self.override = patch.object(check_b, 'ROOT', self.root)
        self.override.start()

    def tearDown(self):
        self.override.stop()
        self.temp.cleanup()

    def mutate(self, path, change):
        p = self.root/path
        data = json.loads(p.read_text())
        change(data)
        p.write_text(json.dumps(data))

    def gate(self):
        gate = check_b.Gate()
        gate.run()
        return gate

    def test_pristine_sources(self):
        gate = self.gate()
        self.assertFalse(any(gate.errors.values()), gate.errors)
        self.assertTrue(gate.pdf_state.startswith('SKIP'))

    def test_g1_each_split_independent(self):
        def remove(data):
            for line in data['lines']:
                if line['split'] == 'calibration' and line['outcome'] == 'supported':
                    line['outcome'] = 'unsupported'
        self.mutate('truth_b.json', remove)
        errors = self.gate().errors['G1']
        self.assertTrue(errors)
        self.assertTrue(all('calibration' in e for e in errors))

    def test_g2_multiple_labels(self):
        self.mutate('truth_b.json', lambda d:d['lines'][0].update(claim_type=['claims_afe', 'no_claim']))
        self.assertTrue(self.gate().errors['G2'])

    def test_g3_register_status(self):
        self.mutate('reference/afe_register.json', lambda d:d[0].update(status='declined'))
        self.assertTrue(self.gate().errors['G3'])

    def test_g4_arithmetic(self):
        self.mutate('truth_b.json', lambda d:d['lines'][0].update(gross=1))
        self.assertTrue(self.gate().errors['G4'])

    def test_g5_partial_render_fails(self):
        (self.root/'clean/cal_jib_01.pdf').write_bytes(b'fixture')
        with patch.object(check_b.subprocess, 'run', side_effect=ValueError('invalid PDF fixture')):
            gate = self.gate()
        self.assertTrue(gate.errors['G5'])
        self.assertEqual(gate.pdf_state, 'CHECKED')

    def test_g6_afe_leakage(self):
        self.mutate('reference/afe_register.json', lambda d:d[0].update(split='scored'))
        self.assertTrue(self.gate().errors['G6'])

    def test_g7_missing_property(self):
        self.mutate('reference/afe_register.json', lambda d:d[0].update(property_no=''))
        self.assertTrue(self.gate().errors['G7'])

    def test_g8_missing_remark_target(self):
        self.mutate('truth_b.json', lambda d:d['remarks'][0].update(names_line=999))
        self.assertTrue(self.gate().errors['G8'])

    def test_g9_bad_literal(self):
        def change(data):
            line = next(l for l in data['lines'] if l['placeholder_style'] == 'literal')
            line['claim_text'] = 'Approved AFE: NA'
        self.mutate('truth_b.json', change)
        self.assertTrue(self.gate().errors['G9'])

    def test_source_cell_tamper(self):
        p = self.root/'sources/cal_jib_01.html'
        p.write_text(p.read_text().replace('1,638.80', '1,638.81'))
        gate = self.gate()
        self.assertTrue(gate.errors['G2'])
        self.assertTrue(gate.errors['G4'])


class BoundingBoxTests(unittest.TestCase):
    def test_wrapped_cells_and_line_remark(self):
        page = ET.Element('page', width='612', height='792')
        def word(text, x, y):
            ET.SubElement(page, 'word', xMin=str(x), xMax=str(x+12), yMin=str(y), yMax=str(y+7)).text = text
        positions = [42, 63, 108, 240, 354, 432, 480, 528]
        for text, x in zip(check_b.HEADERS, positions):
            word(text, x, 150)
        # XML order deliberately interleaves columns and reverses wrapped words.
        word('continued', 240, 184)
        word('second', 108, 184)
        for text, x in zip(['1', 'PR6812', 'First', 'Reference', 'Vendor', '10.00', '0.187500', '1.88'], positions):
            word(text, x, 172)
        word('Page', 42, 210)
        word('totals', 70, 210)
        word('Gross:', 350, 210)
        word('10.00', 390, 210)
        word('Net:', 480, 210)
        word('1.88', 520, 210)
        word('Line', 50, 245)
        word('1:', 74, 245)
        word('Claim', 90, 245)
        word('continued.', 50, 257)
        word('SYNTHETIC', 42, 760)
        rows, remarks, totals = check_b.extract_page(page)
        self.assertEqual(rows[0][1][2:4], ['First second', 'Reference continued'])
        self.assertEqual(remarks, ['Line 1: Claim continued.'])
        self.assertEqual(totals['Page'], 'Page totals Gross: 10.00 Net: 1.88')
        self.assertEqual(len(rows), 1)

    def test_duplicate_json_labels_rejected(self):
        with self.assertRaises(ValueError):
            json.loads('{"outcome":"supported","outcome":"unsupported"}', object_pairs_hook=check_b.strict_object)


if __name__ == '__main__':
    unittest.main()
