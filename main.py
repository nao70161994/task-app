import json
import os
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.core.window import Window
from kivy.metrics import dp

TASKS_FILE = 'tasks.json'


class TaskApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        self.tasks = self._load()

        root = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        # 入力エリア
        row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(8))
        self.input = TextInput(
            hint_text='新しいタスクを入力...',
            multiline=False,
            font_size=dp(16),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        self.input.bind(on_text_validate=self.add_task)
        add_btn = Button(
            text='追加',
            size_hint_x=None,
            width=dp(80),
            background_color=(0.2, 0.6, 1, 1),
            font_size=dp(16),
        )
        add_btn.bind(on_press=self.add_task)
        row.add_widget(self.input)
        row.add_widget(add_btn)

        # タスクリスト
        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)

        root.add_widget(row)
        root.add_widget(scroll)
        self._render()
        return root

    def add_task(self, *_):
        text = self.input.text.strip()
        if not text:
            return
        self.tasks.append({'text': text, 'done': False})
        self._save()
        self.input.text = ''
        self._render()

    def toggle(self, idx):
        self.tasks[idx]['done'] = not self.tasks[idx]['done']
        self._save()
        self._render()

    def delete(self, idx):
        self.tasks.pop(idx)
        self._save()
        self._render()

    def _render(self):
        self.list_layout.clear_widgets()
        for i, task in enumerate(self.tasks):
            row = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(6))

            check = Button(
                text='✓' if task['done'] else '○',
                size_hint_x=None,
                width=dp(56),
                background_color=(0.2, 0.7, 0.3, 1) if task['done'] else (0.3, 0.3, 0.3, 1),
                font_size=dp(18),
            )
            check.bind(on_press=lambda _, i=i: self.toggle(i))

            lbl = Label(
                text=('[s]' + task['text'] + '[/s]') if task['done'] else task['text'],
                markup=True,
                halign='left',
                valign='middle',
                font_size=dp(16),
                color=(0.6, 0.6, 0.6, 1) if task['done'] else (1, 1, 1, 1),
            )
            lbl.bind(size=lbl.setter('text_size'))

            del_btn = Button(
                text='✕',
                size_hint_x=None,
                width=dp(48),
                background_color=(0.8, 0.2, 0.2, 1),
                font_size=dp(16),
            )
            del_btn.bind(on_press=lambda _, i=i: self.delete(i))

            row.add_widget(check)
            row.add_widget(lbl)
            row.add_widget(del_btn)
            self.list_layout.add_widget(row)

    def _load(self):
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, encoding='utf-8') as f:
                return json.load(f)
        return []

    def _save(self):
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False)


if __name__ == '__main__':
    TaskApp().run()
