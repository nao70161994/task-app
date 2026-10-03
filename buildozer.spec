[app]
title = タスク管理
package.name = taskmanager
package.domain = com.example
source.dir = .
source.exclude_dirs = tests,tools,android
source.exclude_patterns = tasks.json*,*.tmp,*.jks,*.keystore,p4a_hook.py
source.include_exts = py,png,jpg,kv,atlas,json,ttc,ttf,otf
version.regex = APP_VERSION = ['\"](.*)['\"]
version.filename = app_version.py
android.numeric_version = 10200
android.release_artifact = apk
p4a.hook = p4a_hook.py
requirements = python3,kivy,plyer
orientation = portrait
fullscreen = 0
android.permissions = WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,VIBRATE,POST_NOTIFICATIONS,INTERNET
android.minapi = 21
android.ndk = 25b
android.sdk = 33
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
