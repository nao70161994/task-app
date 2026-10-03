"""Validated, atomic task persistence; no Kivy dependency."""
import copy
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4


class StorageError(Exception):
    pass


def normalize_tasks(value):
    if not isinstance(value, list):
        raise StorageError('タスクデータは配列である必要があります')
    tasks = copy.deepcopy(value)
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get('text'), str):
            raise StorageError('タスク名が不正です')
        defaults = dict(done=False, priority='medium', due='', category='',
                        tags=[], repeat='none', subtasks=[])
        for key, default in defaults.items():
            task.setdefault(key, copy.deepcopy(default))
        if type(task['done']) is not bool:
            raise StorageError('完了状態が不正です')
        if task['priority'] not in ('high', 'medium', 'low'):
            raise StorageError('優先度が不正です')
        if task['repeat'] not in ('none', 'daily', 'weekly', 'monthly'):
            raise StorageError('繰り返し設定が不正です')
        if any(not isinstance(task[k], str) for k in ('due', 'category')):
            raise StorageError('期限・カテゴリが不正です')
        if not isinstance(task['tags'], list) or any(not isinstance(t, str) for t in task['tags']):
            raise StorageError('タグが不正です')
        if not isinstance(task['subtasks'], list):
            raise StorageError('サブタスクが不正です')
        for sub in task['subtasks']:
            if not isinstance(sub, dict) or not isinstance(sub.get('text'), str):
                raise StorageError('サブタスク名が不正です')
            sub.setdefault('done', False)
            if type(sub['done']) is not bool:
                raise StorageError('サブタスクの完了状態が不正です')
    return tasks


def _decode(raw):
    try:
        return normalize_tasks(json.loads(raw.decode('utf-8-sig')))
    except (ValueError, UnicodeError) as exc:
        raise StorageError('JSONを読み込めません') from exc


def _atomic_write(path, raw):
    """The original remains intact until a flushed same-directory replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    # Some platforms do not support syncing directories. File data is already synced.
    try:
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError:
        pass


class TaskStore:
    def __init__(self, path, legacy_path=None):
        self.path = Path(path).absolute()
        self.backup = self.path.with_name(self.path.name + '.bak')
        self.legacy = Path(legacy_path).absolute() if legacy_path else None
        self.blocked = False
        self.notice = ''

    def load(self):
        self.blocked = False
        self.notice = ''
        # Prefer canonical storage; an old legacy file must never resurrect deleted tasks.
        source = self.path
        if not self.path.exists() and not self.backup.exists() and self.legacy and self.legacy != self.path:
            source = self.legacy
        backup = source.with_name(source.name + '.bak')
        if not source.exists() and not backup.exists():
            return []
        try:
            raw = source.read_bytes()
            tasks = _decode(raw)
        except (OSError, StorageError) as primary_error:
            try:
                raw = backup.read_bytes()
                tasks = _decode(raw)
                if source.exists():
                    # Preserve exact bytes, never truncate the damaged original.
                    _atomic_write(source.with_name(source.name + '.corrupt-' + uuid4().hex), source.read_bytes())
                _atomic_write(self.path, raw)
                if source != self.path:
                    _atomic_write(self.backup, raw)
                self.notice = 'タスクデータをバックアップから復旧しました。'
                return tasks
            except (OSError, StorageError) as recovery_error:
                self.blocked = True
                self.notice = ('タスクデータを読み込めません。元データを保護するため保存を停止しました。'
                               ' tasks.json と .bak を保管して復旧してください。')
                return []
        if source != self.path:
            try:
                # Copy exact legacy bytes, retaining the original and a migration backup.
                _atomic_write(self.backup, raw)
                _atomic_write(self.path, raw)
                self.notice = '既存のタスクデータを引き継ぎました。元ファイルも保持しています。'
            except OSError as exc:
                self.blocked = True
                self.notice = 'データ移行を保存できません。元データを保持し、保存を停止しました。'
        return tasks

    def save(self, tasks):
        if self.blocked:
            raise StorageError(self.notice)
        validated = normalize_tasks(tasks)
        raw = json.dumps(validated, ensure_ascii=False, allow_nan=False).encode('utf-8')
        try:
            if self.path.exists():
                previous = self.path.read_bytes()
                _decode(previous)  # Never rotate a damaged primary over the good backup.
                _atomic_write(self.backup, previous)
            _atomic_write(self.path, raw)
        except (OSError, ValueError) as exc:
            raise StorageError('保存できませんでした。前回保存したデータを保持しています。') from exc
