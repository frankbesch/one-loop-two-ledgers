#!/usr/bin/env python3
"""Non-rendering regression tests for the build gate's rejection paths."""
import unittest
from pathlib import Path

import build_b as b
from check_b import Gate


class GateTests(unittest.TestCase):
    def setUp(self):
        self.gate = Gate(sources_only=True)

    def rejects(self, number):
        with self.assertRaises(ValueError):
            getattr(self.gate, f'g{number}')()

    def test_g1_missing_quota(self):
        self.gate.lines = [r for r in self.gate.lines if r['reference_kind'] != 'unknown_number']
        self.rejects(1)

    def test_g2_missing_label(self):
        del self.gate.lines[0]['outcome']
        self.rejects(2)

    def test_g2_duplicate_json_label(self):
        with self.assertRaises(ValueError):
            b.unique_object([('outcome', 'supported'), ('outcome', 'unsupported')])

    def test_g3_register_disagreement(self):
        row = next(r for r in self.gate.lines if r['property_match'] == 'mismatch')
        row['property_match'] = 'match'
        row['outcome'] = 'supported'
        self.rejects(3)

    def test_g3_unknown_number_in_register(self):
        self.gate.register.append(dict(self.gate.register[0], afe_number='HZR:00719:00628'))
        self.rejects(3)

    def test_g4_wrong_net(self):
        self.gate.lines[0]['net'] += .01
        self.rejects(4)

    def test_g4_wrong_total(self):
        self.gate.manifest['documents'][0]['net_total'] = '0.00'
        self.rejects(4)

    def test_half_even_preserves_fixed_spec(self):
        self.assertEqual(b.cents(b.decimal('2078.32') * b.decimal('.1875')), b.decimal('389.68'))
        self.assertEqual(b.cents(b.decimal('13022.96') * b.decimal('.1875')), b.decimal('2441.80'))
        self.gate.g4()

    def test_g5_empty_clean_skips(self):
        self.gate.sources_only = False
        self.gate.pdfs = []
        self.assertIn('SKIP', self.gate.g5())
        self.assertIn('UNVERIFIED', self.gate.g5())

    def test_g5_partial_clean_fails(self):
        self.gate.sources_only = False
        self.gate.pdfs = [Path('smk_jib_01.pdf')]
        self.rejects(5)

    def test_g5_missing_claim_fails(self):
        self.gate.sources_only = False
        self.gate.pdfs = [Path(d + '.pdf') for d in self.gate.docs]
        # Mock extracted text only; no PDFs are created or rendered by these tests.
        self.gate.pdf_rows = lambda doc: {r['line_no']: {'reference': '', 'description': ''} for r in doc['lines']}
        self.gate.pdf = lambda doc_id: [[]]
        self.rejects(5)

    def test_g5_missing_remark_fails(self):
        self.gate.sources_only = False
        self.gate.pdfs = [Path(d + '.pdf') for d in self.gate.docs]
        self.gate.pdf_rows = lambda doc: {}
        self.gate.pdf = lambda doc_id: [[]]
        for row in self.gate.lines:
            row['claim_text'] = None
        self.rejects(5)

    def test_g6_shared_document(self):
        self.gate.spec['documents'].append(dict(self.gate.spec['documents'][0], split='second'))
        self.rejects(6)

    def test_g6_shared_canonical_afe(self):
        row = next(r for r in self.gate.lines if r['reference_kind'] == 'reformatted')
        row['split'] = 'second'
        self.rejects(6)

    def test_g7_missing_property(self):
        del self.gate.lines[0]['property']
        self.rejects(7)

    def test_g7_wrong_property_matches(self):
        row = next(r for r in self.gate.lines if r['property_match'] == 'mismatch')
        row['property'] = row['property_no'] = 'PX/381'
        self.rejects(7)

    def test_g8_missing_target(self):
        self.gate.remarks[0]['names_line'] = 999
        self.rejects(8)

    def test_g8_claim_not_only_in_remark(self):
        row = next(r for r in self.gate.lines if r['difficulty'] == 'hard')
        row['description'] += ' ' + row['claim_text']
        self.rejects(8)

    def test_g8_pdf_row_split_or_truncated(self):
        self.gate.sources_only = False
        self.gate.pdfs = [Path('smk_jib_01.pdf')]
        self.gate.pdf_rows = lambda doc: {r['line_no']: {field: '' for field in ('line_no', 'property_no', 'vendor', 'description', 'reference')} for r in doc['lines']}
        self.rejects(8)

    def test_g9_bad_literal(self):
        row = next(r for r in self.gate.lines if r['placeholder_style'] == 'literal')
        row['reference'] = 'T.B.D.'
        self.rejects(9)

    def test_g9_literal_in_paraphrase(self):
        row = next(r for r in self.gate.lines if r['placeholder_style'] == 'paraphrased')
        row['reference'] = 'Identifier Pending entry'
        self.rejects(9)


if __name__ == '__main__':
    unittest.main()
