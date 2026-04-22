import json
import os
import calendar
from datetime import date, timedelta
from threading import Thread
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
APP_VERSION = '1.1'
GITHUB_REPO = 'nao70161994/task-app'

PRIORITY_COLORS = {
    'high':   (0.9, 0.2, 0.2, 1),
    'medium': (0.9, 0.6, 0.1, 1),
    'low':    (0.2, 0.7, 0.3, 1),
}
PRIORITY_LABELS = {'high': '高', 'medium': '中', 'low': '低'}
PRIORITY_CYCLE  = ['high', 'medium', 'low']

REPEAT_OPTIONS = ['なし', '毎日', '毎週', '毎月']
REPEAT_VALUES  = {'なし': 'none', '毎日': 'daily', '毎週': 'weekly', '毎月': 'monthly'}
REPEAT_LABELS  = {v: k for k, v in REPEAT_VALUES.items()}

TAG_COLORS = [
    (0.6, 0.2, 0.8, 1),
    (0.2, 0.7, 0.5, 1),
    (0.8, 0.4, 0.1, 1),
    (0.2, 0.4, 0.9, 1),
    (0.7, 0.1, 0.5, 1),
]


def _next_due(due_str, repeat):
    if not due_str or repeat == 'none':
        return due_str
    try:
        d = date.fromisoformat(due_str)
    except ValueError:
        return due_str
    if repeat == 'daily':
        d += timedelta(days=1)
    elif repeat == 'weekly':
        d += timedelta(weeks=1)
    elif repeat == 'monthly':
        month = d.month + 1
        year = d.year + (month - 1) // 12
        month = ((month - 1) % 12) + 1
        max_day = calendar.monthrange(year, month)[1]
        d = d.replace(year=year, month=month, day=min(d.day, max_day))
    return d.isoformat()


class TaskApp(App):
    def build(self):
        from kivy.core.text import LabelBase
        if os.path.exists('NotoSansCJK-Regular.ttc'):
            LabelBase.register(name='Roboto', fn_regular='NotoSansCJK-Regular.ttc')

        Window.clearcolor = (0.1, 0.1, 0.1, 1)
        self.tasks = self._load()
        self.search_text = ''
        self.filter_category = ''
        self.filter_priority = ''
        self.filter_tag = ''
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

        # ── タグフィルター（横スクロール） ────────────────────
        tag_scroll = ScrollView(size_hint_y=None, height=dp(32), do_scroll_y=False)
        self.tag_row = BoxLayout(size_hint_x=None, height=dp(32), spacing=dp(4))
        self.tag_row.bind(minimum_width=self.tag_row.setter('width'))
        tag_scroll.add_widget(self.tag_row)

        # ── タスクリスト ──────────────────────────────────────
        scroll = ScrollView()
        self.list_layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        scroll.add_widget(self.list_layout)

        root.add_widget(search_row)
        root.add_widget(action_row)
        root.add_widget(cat_scroll)
        root.add_widget(tag_scroll)
        root.add_widget(scroll)
        self._render()
        self._notify_due()
        Thread(target=self._check_update, daemon=True).start()
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

    def _set_tag_filter(self, tag):
        self.filter_tag = tag
        self._render()

    # ── 通知 ─────────────────────────────────────────────────

    def _notify_due(self):
        try:
            from plyer import notification
            today = date.today().isoformat()
            due_today = [t for t in self.tasks if t.get('due') == today and not t['done']]
            overdue   = [t for t in self.tasks if t.get('due') and t['due'] < today and not t['done']]
            msgs = []
            if due_today:
                msgs.append(f'今日期限: {len(due_today)}件')
            if overdue:
                msgs.append(f'期限切れ: {len(overdue)}件')
            if msgs:
                notification.notify(
                    title='タスクリマインダー',
                    message=' / '.join(msgs),
                    app_name='TaskApp',
                    timeout=5,
                )
        except Exception:
            pass

    # ── バージョンチェック ────────────────────────────────────

    def _check_update(self):
        try:
            import urllib.request
            import json as _json
            url = f'https://api.github.com/repos/{GITHUB_REPO}/releases/latest'
            req = urllib.request.Request(url, headers={'User-Agent': 'TaskApp'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = _json.loads(r.read())
            latest = data.get('tag_name', '').lstrip('v')
            release_url = data.get('html_url', '')
            if latest and self._version_gt(latest, APP_VERSION):
                from kivy.clock import Clock
                Clock.schedule_once(lambda _: self._show_update_popup(latest, release_url))
        except Exception:
            pass

    def _version_gt(self, a, b):
        def to_tuple(v):
            try:
                return tuple(int(x) for x in v.split('.'))
            except ValueError:
                return (0,)
        return to_tuple(a) > to_tuple(b)

    def _show_update_popup(self, new_version, release_url):
        content = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(10))
        content.add_widget(Label(
            text=f'新しいバージョン v{new_version} があります\n（現在: v{APP_VERSION}）',
            font_size=dp(15),
            halign='center',
            color=(1, 1, 1, 1),
        ))
        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        dl_btn = Button(text='ダウンロード', background_color=(0.2, 0.6, 1, 1), font_size=dp(15))
        skip_btn = Button(text='後で', background_color=(0.35, 0.35, 0.35, 1), font_size=dp(14))
        btn_row.add_widget(dl_btn)
        btn_row.add_widget(skip_btn)
        content.add_widget(btn_row)

        popup = Popup(
            title='アップデート',
            content=content,
            size_hint=(0.85, None),
            height=dp(200),
        )

        def on_download(_):
            popup.dismiss()
            try:
                from kivy.utils import platform
                if platform == 'android':
                    from jnius import autoclass
                    PythonActivity = autoclass('org.kivy.android.PythonActivity')
                    Intent = autoclass('android.content.Intent')
                    Uri = autoclass('android.net.Uri')
                    intent = Intent(Intent.ACTION_VIEW)
                    intent.setData(Uri.parse(release_url))
                    PythonActivity.mActivity.startActivity(intent)
                else:
                    import webbrowser
                    webbrowser.open(release_url)
            except Exception:
                pass

        dl_btn.bind(on_press=on_download)
        skip_btn.bind(on_press=lambda _: popup.dismiss())
        popup.open()

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
        repeat_spinner = Spinner(
            text=REPEAT_LABELS.get(task.get('repeat', 'none'), 'なし') if task else 'なし',
            values=REPEAT_OPTIONS,
            size_hint_y=None,
            height=dp(44),
            font_size=dp(15),
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
        tags_input = TextInput(
            text=', '.join(task.get('tags', [])) if task else '',
            hint_text='タグ (カンマ区切り: 仕事, 重要)',
            multiline=False,
            font_size=dp(15),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(44),
        )

        content.add_widget(lbl('タスク名'));   content.add_widget(text_input)
        content.add_widget(lbl('優先度'));     content.add_widget(priority_spinner)
        content.add_widget(lbl('期限日'));     content.add_widget(due_input)
        content.add_widget(lbl('繰り返し'));   content.add_widget(repeat_spinner)
        content.add_widget(lbl('カテゴリ'));   content.add_widget(cat_input)
        content.add_widget(lbl('タグ'));       content.add_widget(tags_input)

        popup_height = dp(530)
        if idx is not None:
            popup_height += dp(46)

        popup = Popup(
            title='タスクを編集' if task else 'タスクを追加',
            content=content,
            size_hint=(0.92, None),
            height=popup_height,
        )

        if idx is not None:
            sub_btn = Button(
                text=f'サブタスク管理 ({len(task.get("subtasks", []))}件)',
                background_color=(0.3, 0.3, 0.5, 1),
                font_size=dp(14),
                size_hint_y=None,
                height=dp(40),
            )
            sub_btn.bind(on_press=lambda _: self._open_subtask_popup(idx, popup))
            content.add_widget(sub_btn)

        btn_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        save_btn   = Button(text='保存',       background_color=(0.2, 0.6, 1, 1),      font_size=dp(16))
        cancel_btn = Button(text='キャンセル', background_color=(0.35, 0.35, 0.35, 1), font_size=dp(15))
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        def on_save(_):
            text = text_input.text.strip()
            if not text:
                return
            raw_tags = [t.strip() for t in tags_input.text.split(',') if t.strip()]
            data = {
                'text':     text,
                'done':     task['done'] if task else False,
                'priority': label_to_pri[priority_spinner.text],
                'due':      due_input.text.strip(),
                'repeat':   REPEAT_VALUES[repeat_spinner.text],
                'category': cat_input.text.strip(),
                'tags':     raw_tags,
                'subtasks': task.get('subtasks', []) if task else [],
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

    # ── サブタスク管理ポップアップ ────────────────────────────

    def _open_subtask_popup(self, task_idx, parent_popup):
        parent_popup.dismiss()
        task = self.tasks[task_idx]

        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(6))

        scroll = ScrollView(size_hint_y=1)
        sub_layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        sub_layout.bind(minimum_height=sub_layout.setter('height'))
        scroll.add_widget(sub_layout)

        def refresh_subs():
            sub_layout.clear_widgets()
            for si, sub in enumerate(task.get('subtasks', [])):
                row = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))
                chk = Button(
                    text='✓' if sub['done'] else '○',
                    size_hint_x=None,
                    width=dp(40),
                    background_color=(0.2, 0.7, 0.3, 1) if sub['done'] else (0.3, 0.3, 0.3, 1),
                    font_size=dp(15),
                )

                def toggle_sub(_, si=si):
                    task['subtasks'][si]['done'] = not task['subtasks'][si]['done']
                    self._save()
                    self._render()
                    refresh_subs()

                chk.bind(on_press=toggle_sub)
                sub_lbl = Label(
                    text=sub['text'],
                    halign='left',
                    valign='middle',
                    font_size=dp(14),
                    color=(0.5, 0.5, 0.5, 1) if sub['done'] else (1, 1, 1, 1),
                )
                sub_lbl.bind(size=sub_lbl.setter('text_size'))
                del_s = Button(
                    text='✕',
                    size_hint_x=None,
                    width=dp(34),
                    background_color=(0.75, 0.2, 0.2, 1),
                    font_size=dp(14),
                )

                def del_sub(_, si=si):
                    task['subtasks'].pop(si)
                    self._save()
                    self._render()
                    refresh_subs()

                del_s.bind(on_press=del_sub)
                row.add_widget(chk)
                row.add_widget(sub_lbl)
                row.add_widget(del_s)
                sub_layout.add_widget(row)

        refresh_subs()

        add_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        new_sub_input = TextInput(
            hint_text='新しいサブタスク',
            multiline=False,
            font_size=dp(14),
            background_color=(0.2, 0.2, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
        )
        add_sub_btn = Button(
            text='追加',
            size_hint_x=None,
            width=dp(70),
            background_color=(0.2, 0.6, 1, 1),
            font_size=dp(14),
        )

        def add_sub(_):
            text = new_sub_input.text.strip()
            if not text:
                return
            task.setdefault('subtasks', []).append({'text': text, 'done': False})
            new_sub_input.text = ''
            self._save()
            self._render()
            refresh_subs()

        add_sub_btn.bind(on_press=add_sub)
        add_row.add_widget(new_sub_input)
        add_row.add_widget(add_sub_btn)

        close_btn = Button(
            text='閉じる',
            size_hint_y=None,
            height=dp(44),
            background_color=(0.35, 0.35, 0.35, 1),
            font_size=dp(15),
        )

        content.add_widget(scroll)
        content.add_widget(add_row)
        content.add_widget(close_btn)

        sub_popup = Popup(
            title=f'サブタスク: {task["text"][:20]}',
            content=content,
            size_hint=(0.92, 0.7),
        )
        close_btn.bind(on_press=lambda _: sub_popup.dismiss())
        sub_popup.open()

    # ── タスク操作 ────────────────────────────────────────────

    def toggle(self, idx):
        task = self.tasks[idx]
        repeat = task.get('repeat', 'none')
        if repeat != 'none' and not task['done']:
            task['due'] = _next_due(task.get('due', ''), repeat)
        else:
            task['done'] = not task['done']
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

        # タグフィルターボタンを再構築
        self.tag_row.clear_widgets()
        tag_all_btn = Button(
            text='#全タグ',
            font_size=dp(11),
            size_hint_x=None,
            width=dp(60),
            background_color=(0.5, 0.2, 0.7, 1) if self.filter_tag == '' else (0.3, 0.3, 0.3, 1),
        )
        tag_all_btn.bind(on_press=lambda _: self._set_tag_filter(''))
        self.tag_row.add_widget(tag_all_btn)

        all_tags = sorted({tag for t in self.tasks for tag in t.get('tags', [])})
        for ti, tag in enumerate(all_tags):
            color = TAG_COLORS[ti % len(TAG_COLORS)]
            w = max(dp(55), dp(len(tag) * 12 + 16))
            tbtn = Button(
                text='#' + tag,
                font_size=dp(11),
                size_hint_x=None,
                width=w,
                background_color=color if self.filter_tag == tag else (0.3, 0.3, 0.3, 1),
            )
            tbtn.bind(on_press=lambda b, tg=tag: self._set_tag_filter(tg))
            self.tag_row.add_widget(tbtn)

        # 表示するタスクを絞り込み
        visible = [
            (i, t) for i, t in enumerate(self.tasks)
            if not (self.hide_done and t['done'])
            and (not self.search_text or self.search_text in t['text'].lower())
            and (not self.filter_priority or t.get('priority', 'medium') == self.filter_priority)
            and (not self.filter_category or t.get('category', '') == self.filter_category)
            and (not self.filter_tag or self.filter_tag in t.get('tags', []))
        ]

        self.list_layout.clear_widgets()
        for i, task in visible:
            tags     = task.get('tags', [])
            subtasks = task.get('subtasks', [])
            repeat   = task.get('repeat', 'none')
            has_mid  = bool(tags) or repeat != 'none'
            has_sub  = bool(subtasks)

            card_height = dp(72)
            if has_mid:
                card_height += dp(22)
            if has_sub:
                card_height += dp(22)

            card = BoxLayout(
                orientation='vertical',
                size_hint_y=None,
                height=card_height,
                padding=(dp(2), dp(2)),
                spacing=dp(2),
            )

            # 上段: チェック | テキスト | 優先度 | 編集 | 削除
            top = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(4))

            if repeat != 'none' and not task['done']:
                check_text  = '↻'
                check_color = (0.2, 0.5, 0.8, 1)
            elif task['done']:
                check_text  = '✓'
                check_color = (0.2, 0.7, 0.3, 1)
            else:
                check_text  = '○'
                check_color = (0.3, 0.3, 0.3, 1)

            check = Button(
                text=check_text,
                size_hint_x=None,
                width=dp(44),
                background_color=check_color,
                font_size=dp(16),
            )
            check.bind(on_press=lambda _, i=i: self.toggle(i))

            task_lbl = Label(
                text=('[s]' + task['text'] + '[/s]') if task['done'] else task['text'],
                markup=True,
                halign='left',
                valign='middle',
                font_size=dp(15),
                color=(0.5, 0.5, 0.5, 1) if task['done'] else (1, 1, 1, 1),
            )
            task_lbl.bind(size=task_lbl.setter('text_size'))

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
            top.add_widget(task_lbl)
            top.add_widget(pri_btn)
            top.add_widget(edit_btn)
            top.add_widget(del_btn)
            card.add_widget(top)

            # 中段: 繰り返し + タグ
            if has_mid:
                mid = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(4))
                if repeat != 'none':
                    rl = Label(
                        text=f'[{REPEAT_LABELS[repeat]}]',
                        size_hint_x=None,
                        width=dp(45),
                        font_size=dp(10),
                        color=(0.4, 0.8, 1.0, 1),
                        halign='center',
                        valign='middle',
                    )
                    rl.bind(size=rl.setter('text_size'))
                    mid.add_widget(rl)
                for ti, tag in enumerate(tags):
                    color = TAG_COLORS[ti % len(TAG_COLORS)]
                    tl = Label(
                        text='#' + tag,
                        size_hint_x=None,
                        width=dp(max(40, len(tag) * 10 + 14)),
                        font_size=dp(10),
                        color=color,
                        halign='center',
                        valign='middle',
                    )
                    tl.bind(size=tl.setter('text_size'))
                    mid.add_widget(tl)
                mid.add_widget(Label())
                card.add_widget(mid)

            # サブタスク進捗行
            if has_sub:
                done_count = sum(1 for s in subtasks if s['done'])
                sub_prog = BoxLayout(size_hint_y=None, height=dp(20), spacing=dp(4))
                sl = Label(
                    text=f'サブ: {done_count}/{len(subtasks)}',
                    halign='left',
                    valign='middle',
                    font_size=dp(11),
                    color=(0.6, 0.9, 0.6, 1),
                )
                sl.bind(size=sl.setter('text_size'))
                sub_prog.add_widget(sl)
                sub_prog.add_widget(Label())
                card.add_widget(sub_prog)

            # 下段: 期限日 | カテゴリ | スペーサー | ↑ | ↓
            bot = BoxLayout(size_hint_y=None, height=dp(24), spacing=dp(4))

            due = task.get('due', '')
            if due:
                if due < today:
                    due_color = (1.0, 0.3, 0.3, 1)
                elif due == today:
                    due_color = (1.0, 0.8, 0.2, 1)
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
            bot.add_widget(Label())
            bot.add_widget(up_btn)
            bot.add_widget(dn_btn)
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
                t.setdefault('tags', [])
                t.setdefault('repeat', 'none')
                t.setdefault('subtasks', [])
            return tasks
        return []

    def _save(self):
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.tasks, f, ensure_ascii=False)


if __name__ == '__main__':
    TaskApp().run()
