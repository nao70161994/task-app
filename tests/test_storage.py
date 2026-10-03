import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from task_storage import TaskStore, StorageError, normalize_tasks


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'data' / 'tasks.json'
        self.store = TaskStore(self.path)
        self.first = [{'text': '買い物 日本語', 'done': False}]
        self.second = [{'text': '次のタスク', 'done': True}]

    def write(self, path, raw):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def test_missing_is_empty_without_creating_file(self):
        self.assertEqual(self.store.load(), [])
        self.assertFalse(self.path.exists())
        self.assertFalse(self.store.blocked)

    def test_round_trip_all_fields_and_unknown_metadata(self):
        tasks = [{**self.first[0], 'priority': 'high', 'due': '2026-10-04',
                  'category': '生活', 'tags': ['重要'], 'repeat': 'monthly',
                  'subtasks': [{'text': '牛乳', 'done': True, 'id': 5}], 'custom': {'id': 8}}]
        original = copy.deepcopy(tasks)
        self.store.save(tasks)
        self.assertEqual(TaskStore(self.path).load(), tasks)
        self.assertEqual(tasks, original)
        self.assertIn('日本語', self.path.read_text())

    def test_legacy_defaults_do_not_modify_source(self):
        legacy = Path(self.temp.name) / 'old' / 'tasks.json'
        raw = b'\xef\xbb\xbf' + json.dumps([{'text': 'old', 'custom': 7}]).encode()
        self.write(legacy, raw)
        store = TaskStore(self.path, legacy)
        result = store.load()
        self.assertEqual(result[0]['done'], False)
        self.assertEqual(result[0]['subtasks'], [])
        self.assertEqual(result[0]['custom'], 7)
        self.assertEqual(legacy.read_bytes(), raw)
        self.assertEqual(store.backup.read_bytes(), raw)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_canonical_empty_wins_over_legacy(self):
        legacy = Path(self.temp.name) / 'tasks.json'
        self.write(legacy, json.dumps(self.first).encode())
        self.store.save([])
        self.assertEqual(TaskStore(self.path, legacy).load(), [])

    def test_backup_keeps_previous_successful_snapshot(self):
        self.store.save(self.first)
        previous = self.path.read_bytes()
        self.store.save(self.second)
        self.assertEqual(self.store.backup.read_bytes(), previous)
        self.assertEqual(self.store.load()[0]['text'], self.second[0]['text'])

    def test_corrupt_primary_recovers_and_preserves_exact_bytes(self):
        self.store.save(self.first)
        self.store.save(self.second)
        broken = b'{broken\xff'
        self.path.write_bytes(broken)
        tasks = self.store.load()
        self.assertEqual(tasks[0]['text'], self.first[0]['text'])
        quarantines = list(self.path.parent.glob('tasks.json.corrupt-*'))
        self.assertEqual(len(quarantines), 1)
        self.assertEqual(quarantines[0].read_bytes(), broken)
        self.assertEqual(TaskStore(self.path).load(), tasks)
        self.assertFalse(self.store.blocked)
        self.assertTrue(self.store.notice)

    def test_missing_primary_recovers_backup(self):
        self.store.save(self.first)
        self.store.save(self.second)
        self.path.unlink()
        self.assertEqual(self.store.load()[0]['text'], self.first[0]['text'])

    def test_invalid_primary_does_not_fall_back_to_stale_legacy(self):
        self.write(self.path, b'{bad')
        legacy = Path(self.temp.name) / 'tasks.json'
        self.write(legacy, json.dumps(self.first).encode())
        store = TaskStore(self.path, legacy)
        self.assertEqual(store.load(), [])
        self.assertTrue(store.blocked)
        with self.assertRaises(StorageError):
            store.save([])
        self.assertEqual(self.path.read_bytes(), b'{bad')

    def test_corrupt_primary_and_backup_are_read_only(self):
        self.write(self.path, b'{bad')
        self.write(self.store.backup, b'null')
        self.assertEqual(self.store.load(), [])
        self.assertTrue(self.store.blocked)
        with self.assertRaises(StorageError):
            self.store.save([])
        self.assertEqual(self.path.read_bytes(), b'{bad')
        self.assertEqual(self.store.backup.read_bytes(), b'null')

    def test_partial_invalid_task_is_never_silently_dropped(self):
        raw = json.dumps([self.first[0], {'text': 5}]).encode()
        self.write(self.path, raw)
        self.assertEqual(self.store.load(), [])
        self.assertTrue(self.store.blocked)
        self.assertEqual(self.path.read_bytes(), raw)

    def test_invalid_schema_variants(self):
        invalid = [None, {}, [None], [{'done': True}], [{'text': 'x', 'done': 'false'}],
                   [{'text': 'x', 'priority': 'unknown'}], [{'text': 'x', 'tags': 'tag'}],
                   [{'text': 'x', 'tags': [1]}], [{'text': 'x', 'subtasks': [None]}],
                   [{'text': 'x', 'subtasks': [{'text': 's', 'done': 1}]}],
                   [{'text': 'x', 'category': None}], [{'text': 'x', 'repeat': 'yearly'}]]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(StorageError):
                normalize_tasks(value)

    def test_optional_subtask_done_default(self):
        tasks = normalize_tasks([{'text': 'x', 'subtasks': [{'text': 's', 'id': 1}]}])
        self.assertEqual(tasks[0]['subtasks'][0], {'text': 's', 'id': 1, 'done': False})

    def test_replace_failure_preserves_primary_and_cleans_temp(self):
        self.store.save(self.first)
        before = self.path.read_bytes()
        real_replace = os.replace
        def replace(source, dest):
            if Path(dest) == self.path:
                raise OSError('disk error')
            return real_replace(source, dest)
        with patch('task_storage.os.replace', side_effect=replace), self.assertRaises(StorageError):
            self.store.save(self.second)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.store.backup.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_backup_failure_aborts_primary_save(self):
        self.store.save(self.first)
        before = self.path.read_bytes()
        with patch('task_storage.os.replace', side_effect=OSError('full')), self.assertRaises(StorageError):
            self.store.save(self.second)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_fsync_failure_aborts_replace(self):
        self.store.save(self.first)
        before = self.path.read_bytes()
        with patch('task_storage.os.fsync', side_effect=OSError('full')), self.assertRaises(StorageError):
            self.store.save(self.second)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_damaged_primary_never_overwrites_good_backup_on_save(self):
        self.store.save(self.first)
        self.store.save(self.second)
        good = self.store.backup.read_bytes()
        self.path.write_bytes(b'bad')
        with self.assertRaises(StorageError):
            self.store.save([])
        self.assertEqual(self.store.backup.read_bytes(), good)
        self.assertEqual(self.path.read_bytes(), b'bad')

    def test_migration_failure_keeps_source_and_blocks_writes(self):
        legacy = Path(self.temp.name) / 'tasks.json'
        raw = json.dumps(self.first).encode()
        self.write(legacy, raw)
        store = TaskStore(self.path, legacy)
        with patch('task_storage.os.replace', side_effect=OSError('full')):
            self.assertEqual(store.load()[0]['text'], self.first[0]['text'])
        self.assertTrue(store.blocked)
        self.assertEqual(legacy.read_bytes(), raw)

    def test_recovery_failure_does_not_overwrite_corrupt_file(self):
        self.store.save(self.first)
        self.store.save(self.second)
        self.path.write_bytes(b'bad')
        with patch('task_storage.os.replace', side_effect=OSError('full')):
            self.assertEqual(self.store.load(), [])
        self.assertTrue(self.store.blocked)
        self.assertEqual(self.path.read_bytes(), b'bad')

    def test_recovers_legacy_backup_when_legacy_corrupt(self):
        legacy = Path(self.temp.name) / 'tasks.json'
        self.write(legacy, b'bad')
        self.write(legacy.with_name('tasks.json.bak'), json.dumps(self.first).encode())
        store = TaskStore(self.path, legacy)
        self.assertEqual(store.load()[0]['text'], self.first[0]['text'])
        self.assertEqual(legacy.read_bytes(), b'bad')
        self.assertTrue(list(legacy.parent.glob('tasks.json.corrupt-*')))
