import java.io.File;
import java.nio.file.Files;
import java.util.Arrays;
import org.kivy.android.TaskDataPreserver;

public class TaskDataPreserverTest {
    static void require(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    public static void main(String[] args) throws Exception {
        File files = Files.createTempDirectory("task-preserve-").toFile();
        File root = new File(files, "app");
        require(root.mkdir(), "create root");
        byte[] task = "[{\"text\":\"日本語\",\"done\":false}]".getBytes("UTF-8");
        byte[] broken = new byte[] {0, -1, 123};
        File source = new File(root, "tasks.json");
        File backup = new File(root, "tasks.json.bak");
        TaskDataPreserver.preserve(root, files); // Fresh install is a no-op.
        require(!new File(files, "task-app-legacy").exists(), "no phantom legacy");
        Files.write(source.toPath(), task);
        Files.write(backup.toPath(), broken);
        TaskDataPreserver.preserve(root, files);
        File safe = new File(files, "task-app-legacy");
        require(Arrays.equals(Files.readAllBytes(new File(safe, "tasks.json").toPath()), task), "exact primary");
        require(Arrays.equals(Files.readAllBytes(new File(safe, "tasks.json.bak").toPath()), broken), "exact corrupt backup");
        require(Arrays.equals(Files.readAllBytes(source.toPath()), task), "original remains");
        Files.write(source.toPath(), broken);
        TaskDataPreserver.preserve(root, files); // Atomic replacement, not a stale first snapshot.
        require(Arrays.equals(Files.readAllBytes(new File(safe, "tasks.json").toPath()), broken), "latest legacy snapshot");
        Files.delete(source.toPath());
        Files.delete(backup.toPath());
        Files.delete(root.toPath()); // Simulate p4a recursiveDelete(files/app).
        require(new File(safe, "tasks.json").isFile(), "survives code cleanup");
        File blocked = Files.createTempDirectory("task-blocked-").toFile();
        File oldRoot = new File(blocked, "app");
        oldRoot.mkdir();
        File old = new File(oldRoot, "tasks.json");
        Files.write(old.toPath(), task);
        Files.write(new File(blocked, "task-app-legacy").toPath(), broken);
        boolean failed = false;
        try { TaskDataPreserver.preserve(oldRoot, blocked); }
        catch (IllegalStateException expected) { failed = true; }
        require(failed, "must block extraction on backup error");
        require(Arrays.equals(Files.readAllBytes(old.toPath()), task), "failure retains original");
        System.out.println("Native legacy data protection tests passed");
    }
}
