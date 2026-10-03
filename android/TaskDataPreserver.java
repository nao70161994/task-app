package org.kivy.android;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;

/** Protect legacy working-directory data BEFORE p4a deletes files/app on update. */
public final class TaskDataPreserver {
    private TaskDataPreserver() {}

    public static void preserve(File appRoot, File filesDir) {
        try {
            File safeDir = new File(filesDir, "task-app-legacy");
            for (String name : new String[] {"tasks.json", "tasks.json.bak"}) {
                File source = new File(appRoot, name);
                if (!source.exists()) continue;
                if (!source.isFile()) throw new IOException("Legacy data is not a file");
                if (!safeDir.isDirectory() && !safeDir.mkdirs()) {
                    throw new IOException("Cannot create legacy backup directory");
                }
                File temporary = File.createTempFile(name + ".", ".tmp", safeDir);
                try {
                    try (FileInputStream input = new FileInputStream(source);
                         FileOutputStream output = new FileOutputStream(temporary)) {
                        byte[] buffer = new byte[8192];
                        int count;
                        while ((count = input.read(buffer)) != -1) {
                            output.write(buffer, 0, count);
                        }
                        output.flush();
                        output.getFD().sync();
                    }
                    if (!temporary.renameTo(new File(safeDir, name))) {
                        throw new IOException("Cannot commit legacy task backup");
                    }
                } finally {
                    if (temporary.exists()) temporary.delete();
                }
            }
        } catch (IOException error) {
            // Fail closed: never proceed to destructive asset extraction without a copy.
            throw new IllegalStateException("Cannot preserve legacy tasks; update startup stopped", error);
        }
    }
}
