"""Fail closed before packaging/publishing a stable release."""
import configparser
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_version import APP_VERSION, VERSION_CODE
from updates import parse_version


def check(tag=None):
    spec = configparser.ConfigParser(interpolation=None)
    spec.read('buildozer.spec')
    app = spec['app']
    version = parse_version(APP_VERSION)
    if version is None or len(APP_VERSION.split('.')) != 3:
        raise ValueError('APP_VERSION must be a stable major.minor.patch version')
    if any(part > 99 for part in version[1:]):
        raise ValueError('minor and patch must be <=99 for versionCode mapping')
    if VERSION_CODE != version[0] * 10000 + version[1] * 100 + version[2]:
        raise ValueError('VERSION_CODE must match major*10000 + minor*100 + patch')
    if app.getint('android.numeric_version') != VERSION_CODE:
        raise ValueError('Android versionCode differs from app_version.py')
    if app.get('version.filename') != 'app_version.py' or app.get('version'):
        raise ValueError('Buildozer must use app_version.py as versionName source')
    match = re.search(app['version.regex'], Path('app_version.py').read_text())
    if not match or match.group(1) != APP_VERSION:
        raise ValueError('Buildozer version regex does not capture APP_VERSION')
    if app['package.domain'] + '.' + app['package.name'] != 'com.example.taskmanager':
        raise ValueError('Existing application ID must be preserved')
    if tag is not None and tag != 'v' + APP_VERSION:
        raise ValueError('Tag must exactly match v' + APP_VERSION)
    return APP_VERSION


if __name__ == '__main__':
    print(check(sys.argv[1] if len(sys.argv) > 1 else None))
