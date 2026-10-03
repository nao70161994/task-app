import copy
import io
import json
import unittest
from urllib.error import HTTPError

from updates import fetch_update, parse_version, release_update, version_gt


def release():
    prefix = 'https://github.com/nao70161994/task-app/releases/'
    return dict(tag_name='v1.2.0', draft=False, prerelease=False,
                html_url=prefix + 'tag/v1.2.0',
                assets=[dict(name='taskmanager-1.2.0-release.apk', size=123, state='uploaded',
                             browser_download_url=prefix + 'download/v1.2.0/taskmanager-1.2.0-release.apk')])


class UpdateTests(unittest.TestCase):
    def test_numeric_comparison_and_legacy_padding(self):
        for candidate, current, expected in [('1.10', '1.9', True), ('1.1.0', '1.1', False),
                ('v1.2.0', '1.1', True), ('1.1', '1.1.0', False), ('2.0', '1.99.99', True),
                ('1.2.0', '1.2.1', False), ('1.2.1', '1.2.0', True)]:
            with self.subTest(candidate=candidate, current=current):
                self.assertEqual(version_gt(candidate, current), expected)

    def test_invalid_versions_never_notify(self):
        for invalid in ['', None, 5, 'vv1.2.0', '1', '1.02', '01.2', '1.2.3.4',
                        '1.2.0-rc.1', '1.2.0+build', '1.2.0\n', ' 1.2.0', 'v', '../2.0']:
            with self.subTest(invalid=invalid):
                self.assertIsNone(parse_version(invalid))
                self.assertFalse(version_gt(invalid, '1.1'))
                self.assertFalse(version_gt('2.0', invalid))

    def test_stable_release_with_apk(self):
        self.assertEqual(release_update(release(), '1.1'),
                         ('1.2.0', release()['html_url']))
        self.assertIsNone(release_update(release(), '1.2'))

    def test_invalid_release_payloads(self):
        cases = [None, [], {}, 'bad']
        for field, value in [('draft', True), ('prerelease', True), ('draft', None),
                             ('tag_name', 'v1.2.0-rc1'), ('html_url', 'https://evil.example'),
                             ('assets', []), ('assets', None), ('assets', [None])]:
            data = release()
            data[field] = value
            cases.append(data)
        for case in cases:
            with self.subTest(case=case):
                self.assertIsNone(release_update(case, '1.1'))

    def test_invalid_or_debug_asset_never_notifies(self):
        for field, value in [('name', 'task-debug.apk'), ('size', 0), ('size', '123'),
                             ('state', 'new'), ('browser_download_url', 'https://evil.example')]:
            data = release()
            data['assets'][0][field] = value
            self.assertIsNone(release_update(data, '1.1'))

    def test_fetch_success_and_timeout_contract(self):
        def opener(request, timeout):
            self.assertEqual(timeout, 8)
            self.assertTrue(request.full_url.endswith('/releases/latest'))
            return io.BytesIO(json.dumps(release()).encode())
        self.assertIsNotNone(fetch_update('1.1', opener))

    def test_network_failure_is_nonfatal(self):
        for error in [TimeoutError(), OSError('offline'), HTTPError('url', 403, 'limit', None, None)]:
            def opener(*args, **kwargs):
                raise error
            self.assertIsNone(fetch_update('1.1', opener))

    def test_invalid_json_and_oversized_response(self):
        for raw in [b'{invalid', b'\xff', b'x' * 1_000_001, b'null']:
            self.assertIsNone(fetch_update('1.1', lambda *a, **kw: io.BytesIO(raw)))
