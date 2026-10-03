import configparser
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app_version import APP_VERSION, VERSION_CODE
from tools.check_release import check
from tools.verify_apk import certificate, metadata, validate


class ReleaseTests(unittest.TestCase):
    def test_source_and_buildozer_versions_match(self):
        self.assertEqual(check('v' + APP_VERSION), APP_VERSION)

    def test_wrong_tag_fails(self):
        for tag in ['v1.1', APP_VERSION, 'v1.2.0-rc1']:
            with self.assertRaises(ValueError):
                check(tag)

    def test_mismatched_version_code_fails(self):
        with patch('tools.check_release.VERSION_CODE', 1), self.assertRaises(ValueError):
            check()

    def test_apk_metadata_parser(self):
        self.assertEqual(metadata("package: name='com.example.taskmanager' versionCode='10100' versionName='1.1' platformBuildVersionName=''"),
                         ('com.example.taskmanager', 10100, '1.1'))
        with self.assertRaises(ValueError):
            metadata('missing')

    def test_verified_certificate_parser(self):
        digest = 'a' * 64
        self.assertEqual(certificate('Signer #1 certificate SHA-256 digest: ' + digest), digest)
        for invalid in ['unsigned', 'Signer #1 certificate SHA-256 digest: abc',
                        '\n'.join('Signer #'+str(i)+' certificate SHA-256 digest: '+digest for i in (1, 2))]:
            with self.assertRaises(ValueError):
                certificate(invalid)

    def test_same_signature_increasing_version_is_required(self):
        new = ('com.example.taskmanager', VERSION_CODE, APP_VERSION)
        old = ('com.example.taskmanager', 10100, '1.1')
        digest = 'a' * 64
        validate(new, old, digest, digest, ':'.join(['AA'] * 32))
        cases = [((new[0], new[1], '1.1'), old, digest, digest, digest),
                 (new, (old[0], VERSION_CODE, old[2]), digest, digest, digest),
                 (new, ('other.app', old[1], old[2]), digest, digest, digest),
                 (new, old, 'b' * 64, digest, digest), (new, old, digest, digest, ''),
                 (new, old, digest, 'b' * 64, digest)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                validate(*args)

    def test_task_data_and_secrets_are_excluded_from_apk(self):
        spec = configparser.ConfigParser(interpolation=None)
        spec.read('buildozer.spec')
        patterns = spec['app']['source.exclude_patterns']
        self.assertIn('tasks.json*', patterns)
        self.assertIn('*.keystore', patterns)
