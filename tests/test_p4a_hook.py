import unittest
from p4a_hook import MARKER, UNPACK, patch_activity


class HookTests(unittest.TestCase):
    def test_inserts_preservation_before_destructive_extraction(self):
        result = patch_activity('before\n            ' + UNPACK + '\nafter')
        self.assertIn(MARKER + '\n            ' + UNPACK, result)
        self.assertEqual(patch_activity(result), result)

    def test_unknown_bootstrap_fails_closed(self):
        for source in ['', UNPACK + UNPACK, UNPACK.replace('true', 'false'), MARKER + UNPACK]:
            with self.subTest(source=source), self.assertRaises(RuntimeError):
                patch_activity(source)
