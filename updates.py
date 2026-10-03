"""Strict stable-release comparison and GitHub response validation."""
import json
import re
import urllib.request

GITHUB_REPO = 'nao70161994/task-app'
_PATTERN = re.compile(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?\Z')


def parse_version(value):
    if not isinstance(value, str):
        return None
    match = _PATTERN.fullmatch(value)
    return tuple(int(part or 0) for part in match.groups()) if match else None


def version_gt(candidate, current):
    left, right = parse_version(candidate), parse_version(current)
    return left is not None and right is not None and left > right


def release_update(data, current):
    if not isinstance(data, dict) or data.get('draft') is not False or data.get('prerelease') is not False:
        return None
    tag = data.get('tag_name')
    if not version_gt(tag, current):
        return None
    # Derive the destination from a validated tag; never open an arbitrary API URL.
    url = f'https://github.com/{GITHUB_REPO}/releases/tag/{tag}'
    if data.get('html_url') != url:
        return None
    assets = data.get('assets')
    if not isinstance(assets, list):
        return None
    prefix = f'https://github.com/{GITHUB_REPO}/releases/download/{tag}/'
    if not any(isinstance(a, dict) and isinstance(a.get('name'), str)
               and a['name'].endswith('-release.apk') and a.get('state') == 'uploaded'
               and isinstance(a.get('size'), int) and a['size'] > 0
               and a.get('browser_download_url') == prefix + a['name'] for a in assets):
        return None
    return tag.removeprefix('v'), url


def fetch_update(current, opener=None):
    try:
        request = urllib.request.Request(
            f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest',
            headers={'User-Agent': 'TaskApp', 'Accept': 'application/vnd.github+json'})
        with (opener or urllib.request.urlopen)(request, timeout=8) as response:
            raw = response.read(1_000_001)
        if len(raw) > 1_000_000:
            return None
        return release_update(json.loads(raw), current)
    except (OSError, ValueError, TypeError):
        return None
