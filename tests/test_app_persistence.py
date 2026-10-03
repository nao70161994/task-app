"""Exercise actual UI mutation methods without requiring a graphical Kivy runtime."""
import copy
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from task_storage import StorageError, TaskStore


def load_app_class():
    stubs = {}
    classes = {'kivy.app': 'App', 'kivy.uix.boxlayout': 'BoxLayout',
               'kivy.uix.textinput': 'TextInput', 'kivy.uix.button': 'Button',
               'kivy.uix.label': 'Label', 'kivy.uix.scrollview': 'ScrollView',
               'kivy.uix.gridlayout': 'GridLayout', 'kivy.uix.popup': 'Popup',
               'kivy.uix.spinner': 'Spinner'}
    for module_name, class_name in classes.items():
        module = types.ModuleType(module_name)
        setattr(module, class_name, type(class_name, (), {}))
        stubs[module_name] = module
    window = types.ModuleType('kivy.core.window')
    window.Window = types.SimpleNamespace()
    metrics = types.ModuleType('kivy.metrics')
    metrics.dp = lambda x: x
    stubs.update({'kivy.core.window': window, 'kivy.metrics': metrics})
    spec = importlib.util.spec_from_file_location('task_app_under_test', 'main.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module.TaskApp


TaskApp = load_app_class()


class AppPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = TaskApp()
        self.app.store = TaskStore(Path(self.temp.name) / 'tasks.json')
        self.app.store.save([{'text': 'first', 'done': False, 'tags': ['tag'],
                              'subtasks': [{'text': 'sub', 'done': False}], 'unknown': 42},
                             {'text': 'second', 'done': True}])
        self.app.tasks = self.app.store.load()
        self.app._saved_tasks = copy.deepcopy(self.app.tasks)
        self.messages = []
        self.app._storage_message = self.messages.append
        self.app._render = lambda: None

    def test_success_updates_snapshot(self):
        self.app.toggle(0)
        self.assertTrue(self.app.tasks[0]['done'])
        self.assertEqual(self.app._saved_tasks, self.app.tasks)
        self.assertEqual(self.app.store.load(), self.app.tasks)

    def test_save_failure_rolls_back_every_top_level_operation(self):
        for operation in [lambda: self.app.toggle(0), lambda: self.app.delete(0),
                          lambda: self.app.move_down(0), lambda: self.app.move_up(1),
                          lambda: self.app._cycle_task_priority(0), self.app._delete_done]:
            with self.subTest(operation=operation):
                before = copy.deepcopy(self.app.tasks)
                with patch.object(self.app.store, 'save', side_effect=StorageError('disk full')):
                    operation()
                self.assertEqual(self.app.tasks, before)
                self.assertEqual(self.app.store.load(), before)
        self.assertEqual(len(self.messages), 6)

    def test_subtask_and_tag_edits_roll_back_as_deep_copy(self):
        before = copy.deepcopy(self.app.tasks)
        self.app.tasks[0]['subtasks'][0]['done'] = True
        self.app.tasks[0]['tags'].append('new')
        with patch.object(self.app.store, 'save', side_effect=StorageError('failure')):
            self.assertFalse(self.app._save())
        self.assertEqual(self.app.tasks, before)
        self.assertEqual(self.app._saved_tasks, before)
        self.assertEqual(self.app.tasks[0]['unknown'], 42)

    def test_blocked_store_rejects_ui_add_without_overwriting(self):
        before = self.app.store.path.read_bytes()
        self.app.store.blocked = True
        self.app.store.notice = 'read only'
        self.app.tasks.append({'text': 'new', 'done': False})
        self.assertFalse(self.app._save())
        self.assertEqual(self.app.store.path.read_bytes(), before)
        self.assertEqual(len(self.app.tasks), 2)
