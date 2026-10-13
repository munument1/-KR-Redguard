import redguard.MapDatabase;
import redguard.MapFile;
import redguard.RtxDatabase;

import java.io.File;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/** Read-only script inspection using the user's independently installed Redguard Mod Manager jar. */
public class RgmInspector {
    public static void main(String[] args) throws Exception {
        if (args.length < 2) {
            System.err.println("Usage: RgmInspector <Redguard-game-directory> <needle> [map-name] [--dump]");
            System.exit(2);
        }
        Path root = Path.of(args[0]);
        String needle = args[1].toLowerCase(Locale.ROOT);
        String mapFilter = args.length >= 3 && !args[2].startsWith("--") ? args[2].toUpperCase(Locale.ROOT) : "";
        boolean dump = Arrays.asList(args).contains("--dump");

        RtxDatabase rtx = new RtxDatabase();
        rtx.readFile(root.resolve("ENGLISH.RTX").toFile());
        MapDatabase database = new MapDatabase(rtx);
        database.readWorldFile(root.resolve("WORLD.INI").toFile());
        database.readSoupFile(root.resolve("soup386/SOUP386.DEF").toFile());
        database.readItemsFile(root.resolve("ITEM.INI").toFile());
        int found = 0;
        for (MapFile map : database.getMapFiles()) {
            if (!mapFilter.isEmpty() && !map.getName().equalsIgnoreCase(mapFilter)) continue;
            File mapFile = root.resolve("maps").resolve(map.getName() + ".RGM").toFile();
            if (!mapFile.exists()) continue;
            try {
                map.readMap(mapFile);
                String[] lines = map.getScript().split("\n", -1);
                System.out.printf("map=%s lines=%d%n", map.getName(), lines.length);
                if (dump) {
                    for (int i = 0; i < lines.length; i++) {
                        System.out.printf("%s\t%d\t%s%n", map.getName(), i, lines[i]);
                    }
                } else {
                    for (int i = 0; i < lines.length; i++) {
                        if (!lines[i].toLowerCase(Locale.ROOT).contains(needle)) continue;
                        found++;
                        for (int j = Math.max(0, i - 4); j <= Math.min(lines.length - 1, i + 5); j++) {
                            System.out.printf("%s\t%d\t%s%n", map.getName(), j, lines[j]);
                        }
                        System.out.println("---");
                    }
                }
            } catch (Exception e) {
                System.err.printf("Could not parse %s: %s%n", map.getName(), e);
            }
        }
        System.out.println("Matches: " + found);
    }
}
