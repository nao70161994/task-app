"""Verify Android metadata and certificate continuity against the prior public APK."""
import argparse
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_version import APP_VERSION, VERSION_CODE


def metadata(text):
    match = re.search(r"package: name='([^']+)' versionCode='([0-9]+)' versionName='([^']+)'", text)
    if not match:
        raise ValueError('Cannot read APK package/version metadata')
    return match.group(1), int(match.group(2)), match.group(3)


def certificate(text):
    hashes = re.findall(r'^Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]{64})$', text, re.M)
    if len(hashes) != 1:
        raise ValueError('Expected one verified APK signing certificate')
    return hashes[0].lower()


def validate(new_meta, previous_meta, new_cert, previous_cert, expected):
    if new_meta != ('com.example.taskmanager', VERSION_CODE, APP_VERSION):
        raise ValueError('New APK package/version does not match source')
    if previous_meta[0] != new_meta[0] or new_meta[1] <= previous_meta[1]:
        raise ValueError('APK must preserve package and increase versionCode')
    expected = expected.lower().replace(':', '')
    if not re.fullmatch('[0-9a-f]{64}', expected) or not (new_cert == previous_cert == expected):
        raise ValueError('Signing certificate mismatch: do not uninstall the existing app')


def inspect(apk, aapt, apksigner):
    meta = subprocess.check_output([aapt, 'dump', 'badging', apk], text=True)
    cert = subprocess.check_output([apksigner, 'verify', '--verbose', '--print-certs', apk], text=True)
    return metadata(meta), certificate(cert)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('new', 'previous', 'aapt', 'apksigner', 'expected'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    new_meta, new_cert = inspect(args.new, args.aapt, args.apksigner)
    old_meta, old_cert = inspect(args.previous, args.aapt, args.apksigner)
    validate(new_meta, old_meta, new_cert, old_cert, args.expected)
    print('Verified package, increasing versionCode, versionName and signing continuity')
