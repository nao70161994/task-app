import json
import os
from datetime import date
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.uix.spinner import Spinner
from kivy.core.window import Window
from kivy.metrics import dp

TASKS_FILE = 'tasks.json'

PRIORITY_COLORS = {
    'high':   (0.9, 0.2, 0.2, 1),
    'medium': (0.9, 0.6, 0.1, 1),
    'low':    (0.2, 0.7, 0.3, 1),
}
PRIORITY_LABELS = {'high': '高', 'medium': '中', 'low': '低'}
PRIORITY_CYCLE  = ['high', 'medium', 'low']


class TaskApp(App):
    def build(self):
        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        self.tasks = self._load()
        self.search_text = ''
        self.filter_category = ''
        self.filter_priority = ''
        self.hide_done = False

        root = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        # ── 検索 + 追加 ──────────────────────────────────────
        search_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(6))
        self.search_input = TextInput(
            hint_text='検索...',
            multiline=False,
            font_size=dp(15),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        self.search_input.bind(text=lambda inst, val: self._set_search(val))
        add_btn = Button(
            text='＋追加',
            size_hint_x=None,
            width=dp(90),
            background_color=(0.2, 0.6, 1, 1),
            font_size=dp(15),
        )
        add_btn.bind(on_press=lambda _: self._open_popup(None))
        search_row.add_widget(self.search_input)
        search_row.add_widget(add_btn)

        # ── アクション行 ──────────────────────────────────────
        action_row = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4))

        self.hide_btn = Button(
            text='完了を隠す',
            font_size=dp(13),
            background_color=(0.3, 0.3, 0.3, 1),
        )
        self.hide_btn.bind(on_press=self._toggle_hide_done)

        self.pri_filter_btn = Button(
            text='優先度: 全て',
            font_size=dp(13),
            background_color=(0.3, 0.3, 0.3, 1),
        )
        self.pri_filter_btn.bind(on_press=self._cycle_priority_filter)

        clear_btn = Button(
            text='完了を削除',
            font_size=dp(13),
            background_color=(0.5, 0.2, 0.2, 1),
        )
        clear_btn.bind(on_press=self._delete_done)

        action_row.add_widget(self.hide_btn)
        action_row.add_widget(self.pri_filter_btn)
        action_row.add_widget(clear_btn)

        # ── カテゴリフィルター（横スクロール） ────────────────
        cat_scroll = ScrollView(size_hint_y=None, height=dp(36), do_scroll_y=False)
        self.cat_row = BoxLayout(size_hint_x=None, height=dp(36), spacing=dp(4))
        self.cat_row.bind(minimum_width=self.cat_row.setter('width'))
        cat_scroll.add_widget(self.cat_row)

        # ── タスクリスト ──────────────────────────────────────
        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)

        root.add_widget(search_row)
        root.add_widget(action_row)
        root.add_widget(cat_scroll)
        root.add_widget(scroll)
        self._render()
        return root

    # ── フィルター操作 ────────────────────────────────────────

    def _set_search(self, val):
        self.search_text = val.lower()
        self._render()

    def _toggle_hide_done(self, *_):
        self.hide_done = not self.hide_done
        self.hide_btn.background_color = (0.2, 0.5, 0.8, 1) if self.hide_done else (0.3, 0.3, 0.3, 1)
        self._render()

    def _cycle_priority_filter(self, *_):
        options = ['', 'high', 'medium', 'low']
        labels  = {'': '優先度: 全て', 'high': '優先度: 高', 'medium': '優先度: 中', 'low': '優先度: 低'}
        idx = options.index(self.filter_priority)
        self.filter_priority = options[(idx + 1) % len(options)]
        self.pri_filter_btn.text = labels[self.filter_priority]
        self.pri_filter_btn.background_color = (
            PRIORITY_COLORS[self.filter_priority] if self.filter_priority else (0.3, 0.3, 0.3, 1)
        )
        self._render()

    def _delete_done(self, *_):
        self.tasks = [t for t in self.tasks if not t['done']]
        self._save()
        self._render()

    def _set_category_filter(self, cat):
        self.filter_category = cat
        self._render()

    # ── 追加・編集ポップアップ ────────────────────────────────

    def _open_popup(self, idx):
        task = self.tasks[idx] if idx is not None else None
        pri_to_label = {'high': '高', 'medium': '中', 'low': '低'}
        label_to_pri = {'高': 'high', '中': 'medium', '低': 'low'}

        content = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(6))

        def lbl(text):
            return Label(text=text, size_hint_y=None, height=dp(22), font_size=dp(13),
                         color=(0.7, 0.7, 0.7, 1), halign='left')

        text_input = TextInput(
            text=task['text'] if task else '',
            hint_text='タスク名',
            multiline=False,
            font_size=dp(16),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(44),
        )
        priority_spinner = Spinner(
            text=pri_to_label.get(task.get('priority', 'medium'), '中') if task else '中',
            values=['高', '中', '低'],
            size_hint_y=None,
            height=dp(44),
            font_size=dp(15),
        )
        due_input = TextInput(
            text=task.get('due', '') if task else '',
            hint_text='期限 (YYYY-MM-DD)',
            multiline=False,
            font_size=dp(15),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(44),
        )
        cat_input = TextInput(
            text=task.get('category', '') if task else '',
            hint_text='カテゴリ',
            multiline=False,
            font_size=dp(15),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(44),
        )
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        save_btn   = Button(text='保存',       background_color=(0.2, 0.6, 1, 1),    font_size=dp(16))
        cancel_btn = Button(text='キャンセル', background_color=(0.35, 0.35, 0.35, 1), font_size=dp(15))
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)

        content.add_widget(lbl('タスク名'));   content.add_widget(text_input)
        content.add_widget(lbl('優先度'));     content.add_widget(priority_spinner)
        content.add_widget(lbl('期限日'));     content.add_widget(due_input)
        content.add_widget(lbl('カテゴリ'));   content.add_widget(cat_input)
        content.add_widget(btn_row)

        popup = Popup(
            title='タスクを編集' if task else 'タスクを追加',
            content=content,
            size_hint=(0.92, None),
            height=dp(430),
        )

        def on_save(_):
            text = text_input.text.strip()
            if not text:
                return
            data = {
                'text':     text,
                'done':     task['done'] if task else False,
                'priority': label_to_pri[priority_spinner.text],
                'due':      due_input.text.strip(),
                'category': cat_input.text.strip(),
            }
            if idx is not None:
                self.tasks[idx] = data
            else:
                self.tasks.append(data)
            self._save()
            self._render()
            popup.dismiss()

        save_btn.bind(on_press=on_save)
        cancel_btn.bind(on_press=lambda _: popup.dismiss())
        popup.open()

    # ── タスク操作 ────────────────────────────────────────────

    def toggle(self, idx):
        self.tasks[idx]['done'] = not self.tasks[idx]['done']
        self._save()
        self._render()

    def delete(self, idx):
        self.tasks.pop(idx)
        self._save()
        self._render()

    def move_up(self, idx):
        if idx > 0:
            self.tasks[idx], self.tasks[idx - 1] = self.tasks[idx - 1], self.tasks[idx]
            self._save()
            self._render()

    def move_down(self, idx):
        if idx < len(self.tasks) - 1:
            self.tasks[idx], self.tasks[idx + 1] = self.tasks[idx + 1], self.tasks[idx]
            self._save()
            self._render()

    def _cycle_task_priority(self, idx):
        cur = self.tasks[idx].get('priority', 'medium')
        nxt = PRIORITY_CYCLE[(PRIORITY_CYCLE.index(cur) + 1) % len(PRIORITY_CYCLE)]
        self.tasks[idx]['priority'] = nxt
        self._save()
        self._render()

    # ── 描画 ──────────────────────────────────────────────────

    def _render(self):
        today = date.today().isoformat()

        # カテゴリフィルターボタンを再構築
        self.cat_row.clear_widgets()
        all_btn = Button(
            text='全て',
            font_size=dp(12),
            size_hint_x=None,
            width=dp(50),
            background_color=(0.2, 0.6, 1, 1) if self.filter_category == '' else (0.3, 0.3, 0.3, 1),
        )
        all_btn.bind(on_press=lambda _: self._set_category_filter(''))
        self.cat_row.add_widget(all_btn)

        cats = sorted({t.get('category', '').strip() for t in self.tasks if t.get('category', '').strip()})
        for cat in cats:
            w = max(dp(60), dp(len(cat) * 14 + 16))
            btn = Button(
                text=cat,
                font_size=dp(12),
                size_hint_x=None,
                width=w,
                background_color=(0.2, 0.6, 1, 1) if self.filter_category == cat else (0.3, 0.3, 0.3, 1),
            )
            btn.bind(on_press=lambda b, c=cat: self._set_category_filter(c))
            self.cat_row.add_widget(btn)

        # 表示するタスクを絞り込み
        visible = [
            (i, t) for i, t in enumerate(self.tasks)
            if not (self.hide_done and t['done'])
            and (not self.search_text or self.search_text in t['text'].lower())
            and (not self.filter_priority or t.get('priority', 'medium') == self.filter_priority)
            and (not self.filter_category or t.get('category', '') == self.filter_category)
        ]

        self.list_layout.clear_widgets()
        for i, task in visible:
            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=dp(72),
                padding=(dp(2), dp(2)),
                spacing=dp(2),
            )

            # 上段: チェック | テキスト | 優先度 | 編集 | 削除
            top = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))

            check = Button(
                text='✓' if task['done'] else '○',
                size_hint_x=None,
                width=dp(44),
                background_color=(0.2, 0.7, 0.3, 1) if task['done'] else (0.3, 0.3, 0.3, 1),
                font_size=dp(16),
            )
            check.bind(on_press=lambda _, i=i: self.toggle(i))

            lbl = Label(
                text=('[s]' + task['text'] + '[/s]') if task['done'] else task['text'],
                markup=True,
                halign='left',
                valign='middle',
                font_size=dp(15),
                color=(0.5, 0.5, 0.5, 1) if task['done'] else (1, 1, 1, 1),
            )
            lbl.bind(size=lbl.setter('text_size'))

            pri = task.get('priority', 'medium')
            pri_btn = Button(
                text=PRIORITY_LABELS[pri],
                size_hint_x=None,
                width=dp(34),
                background_color=PRIORITY_COLORS[pri],
                font_size=dp(12),
            )
            pri_btn.bind(on_press=lambda _, i=i: self._cycle_task_priority(i))

            edit_btn = Button(
                text='✎',
                size_hint_x=None,
                width=dp(34),
                background_color=(0.3, 0.3, 0.55, 1),
                font_size=dp(16),
            )
            edit_btn.bind(on_press=lambda _, i=i: self._open_popup(i))

            del_btn = Button(
                text='✕',
                size_hint_x=None,
                width=dp(34),
                background_color=(0.75, 0.2, 0.2, 1),
                font_size=dp(15),
            )
            del_btn.bind(on_press=lambda _, i=i: self.delete(i))

            top.add_widget(check)
            top.add_widget(lbl)
            top.add_widget(pri_btn)
            top.add_widget(edit_btn)
            top.add_widget(del_btn)

            # 下段: 期限日 | カテゴリ | スペーサー | ↑ | ↓
            bot = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(4))

            due = task.get('due', '')
            if due:
                if due < today:
                    due_color = (1.0, 0.3, 0.3, 1)   # 期限切れ
                elif due == today:
                    due_color = (1.0, 0.8, 0.2, 1)   # 今日
                else:
                    due_color = (0.7, 0.7, 0.7, 1)
            else:
                due_color = (0.5, 0.5, 0.5, 1)

            due_lbl = Label(
                text=('期限: ' + due) if due else '',
                halign='left',
                valign='middle',
                font_size=dp(12),
                color=due_color,
            )
            due_lbl.bind(size=due_lbl.setter('text_size'))

            cat_lbl = Label(
                text=('[' + task['category'] + ']') if task.get('category') else '',
                halign='left',
                valign='middle',
                font_size=dp(12),
                color=(0.4, 0.85, 0.95, 1),
            )
            cat_lbl.bind(size=cat_lbl.setter('text_size'))

            up_btn = Button(
                text='↑',
                size_hint_x=None,
                width=dp(30),
                background_color=(0.3, 0.3, 0.3, 1),
                font_size=dp(13),
            )
            up_btn.bind(on_press=lambda _, i=i: self.move_up(i))

            dn_btn = Button(
                text='↓',
                size_hint_x=None,
                width=dp(30),
                background_color=(0.3, 0.3, 0.3, 1),
                font_size=dp(13),
            )
            dn_btn.bind(on_press=lambda _, i=i: self.move_down(i))

            bot.add_widget(due_lbl)
            bot.add_widget(cat_lbl)
            bot.add_widget(Label())  # spacer
            bot.add_widget(up_btn)
            bot.add_widget(dn_btn)

            card.add_widget(top)
            card.add_widget(bot)
            self.list_layout.add_widget(card)

    # ── 永続化 ────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, encoding='utf-8') as f:
                tasks = json.load(f)
            for t in tasks:
                t.setdefault('priority', 'medium')
                t.setdefault('due', '')
                t.setdefault('category', '')
            return tasks
        return []

    def _save(self):
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False)


if __name__ == '__main__':
    TaskApp().run()
