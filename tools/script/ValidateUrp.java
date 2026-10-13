import redguard.MapChanges;
import redguard.MapDatabase;
import redguard.MapFile;
import redguard.RtxDatabase;

import java.io.File;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/** Verify upstream + Coyle source-map patches compile and roundtrip without editing original game files. */
public class ValidateUrp {
    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("Usage: ValidateUrp <game-dir> <mod-zip>");
            System.exit(2);
        }
        Path root = Path.of(args[0]);
        Path archive = Path.of(args[1]);
        Path changesText = Files.createTempFile("redguard-map-changes-", ".txt");
        try {
            try (ZipFile zip = new ZipFile(archive.toFile())) {
                ZipEntry entry = zip.stream().filter(e -> e.getName().endsWith("/Map Changes.txt")).findFirst().orElseThrow();
                try (InputStream in = zip.getInputStream(entry)) {
                    Files.copy(in, changesText, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
            }
            MapChanges changes = new MapChanges();
            changes.readChanges(changesText.toFile());
            RtxDatabase rtx = new RtxDatabase();
            rtx.readFile(root.resolve("ENGLISH.RTX").toFile());
            MapDatabase database = new MapDatabase(rtx);
            database.readWorldFile(root.resolve("WORLD.INI").toFile());
            database.readSoupFile(root.resolve("soup386/SOUP386.DEF").toFile());
            database.readItemsFile(root.resolve("ITEM.INI").toFile());

            int maps = 0;
            int compiled = 0;
            for (MapFile map : database.getMapFiles()) {
                if (!changes.hasModifiedMap(map.getName())) continue;
                maps++;
                File original = root.resolve("maps").resolve(map.getName() + ".RGM").toFile();
                if (!original.isFile()) throw new IllegalStateException("missing RGM: " + original);
                map.readMap(original);
                String script = map.getModifiedScript(changes);
                if (map.getName().equals("ISLAND")) {
                    String oldLine = "  if after_iszara = 0 and CyrusFriend = 0 and HayleStory = 1";
                    String newLine = "  if CyrusFriend = 0 and HayleStory = 1";
                    if (script.contains(oldLine) || !script.contains(newLine)) {
                        throw new IllegalStateException("Coyle condition missing or old condition remains");
                    }
                }
                Path temp = Files.createTempFile("redguard-" + map.getName() + "-", ".RGM");
                try {
                    map.writeMap(temp.toFile(), script);
                    map.readMap(temp.toFile());
                    String reparsed = map.getScript();
                    if (map.getName().equals("ISLAND")) {
                        if (!reparsed.contains("  if CyrusFriend = 0 and HayleStory = 1")
                                || !reparsed.contains("menuAddItem(\"?hay\", var35, 7)")) {
                            throw new IllegalStateException("Coyle fix lost after RGM recompilation");
                        }
                    }
                    System.out.printf("Compiled and re-read %s: %d bytes%n", map.getName(), Files.size(temp));
                    compiled++;
                } finally {
                    Files.deleteIfExists(temp);
                }
            }
            if (maps == 0 || compiled != maps || !changes.hasModifiedMap("ISLAND")) {
                throw new IllegalStateException("patch validation incomplete");
            }
            System.out.println("Validated " + compiled + " changed maps; original files untouched");
        } finally {
            Files.deleteIfExists(changesText);
        }
    }
}
