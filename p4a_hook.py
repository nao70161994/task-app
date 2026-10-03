"""Install a fail-closed backup BEFORE SDL2 asset extraction deletes files/app."""
from pathlib import Path
import shutil

MARKER = 'TaskDataPreserver.preserve(app_root_file, mActivity.getFilesDir());'
UNPACK = 'PythonUtil.unpackAsset(mActivity, "private", app_root_file, true);'


def patch_activity(source):
    if MARKER in source:
        # Reused distribution: accept only our exact preservation-before-unpack sequence.
        if MARKER + '\n            ' + UNPACK not in source:
            raise RuntimeError('Legacy task protection hook has an unexpected placement')
        return source
    if source.count(UNPACK) != 1:
        raise RuntimeError('Unsupported p4a asset extraction: refusing to build an unsafe upgrade')
    return source.replace(UNPACK, MARKER + '\n            ' + UNPACK)


def before_apk_build(toolchain):
    # p4a invokes this with cwd set to the Android distribution directory.
    java_dir = Path.cwd() / 'src/main/java/org/kivy/android'
    activity = java_dir / 'PythonActivity.java'
    activity.write_text(patch_activity(activity.read_text()))
    shutil.copyfile(Path(__file__).resolve().parent / 'android/TaskDataPreserver.java',
                    java_dir / 'TaskDataPreserver.java')
