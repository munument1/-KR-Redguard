import redguard.MapChanges;
import redguard.MapDatabase;
import redguard.MapFile;
import redguard.RtxDatabase;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.zip.ZipFile;

/** Apply the user's URP map edits and a locally generated Coyle correction. */
public class ExportUrp {
    private static String canonical(String script, boolean vileAlias) {
        var pattern = java.util.regex.Pattern.compile("#[0-9A-F]+\\b");
        StringBuilder result = new StringBuilder();
        for (String block : script.split("(?m)(?=^\\{$)")) {
          var labels = new java.util.HashMap<String, String>();
          var uses = new java.util.HashMap<String, Integer>();
          var allLabels = pattern.matcher(block);
          while (allLabels.find()) uses.merge(allLabels.group(), 1, Integer::sum);
          for (String line : block.split("\\R")) {
            line = line.replaceFirst("\\s*//.*$", "");
            if (line.isBlank()) continue;
            if (line.strip().matches("#[0-9A-F]+:") &&
                uses.getOrDefault(line.strip().replace(":", ""), 0) == 1) continue;
            // The upstream reader resolves this existing VILE object alias on
            // recompilation; it is independent of the after_iszara insertion.
            if (vileAlias) line = line.replaceAll("\\bvile\\.", "viledog.");
            var matcher = pattern.matcher(line);
            StringBuffer normalized = new StringBuffer();
            while (matcher.find()) {
                String label = labels.computeIfAbsent(matcher.group(), k -> "#LABEL" + labels.size());
                matcher.appendReplacement(normalized, label);
            }
            matcher.appendTail(normalized);
            result.append(normalized).append('\n');
          }
        }
        return result.toString();
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 3) throw new IllegalArgumentException("game-dir urp-zip output-dir required");
        Path game = Path.of(args[0]), output = Path.of(args[2]);
        Path changesPath = Files.createTempFile("urp-changes-", ".txt");
        try {
            try (ZipFile zip = new ZipFile(args[1])) {
                var entry = zip.stream().filter(e -> e.getName().endsWith("/Map Changes.txt")).findFirst().orElseThrow();
                try (var in = zip.getInputStream(entry)) {
                    Files.copy(in, changesPath, java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
            }
            MapChanges changes = new MapChanges();
            changes.readChanges(changesPath.toFile());
            RtxDatabase rtx = new RtxDatabase();
            rtx.readFile(game.resolve("ENGLISH.RTX").toFile());
            MapDatabase database = new MapDatabase(rtx);
            database.readWorldFile(game.resolve("WORLD.INI").toFile());
            database.readSoupFile(game.resolve("soup386/SOUP386.DEF").toFile());
            database.readItemsFile(game.resolve("ITEM.INI").toFile());
            Files.createDirectories(output.resolve("maps"));
            int count = 0;
            for (MapFile map : database.getMapFiles()) {
                if (!changes.hasModifiedMap(map.getName())) continue;
                map.readMap(game.resolve("maps").resolve(map.getName() + ".RGM").toFile());
                String script = map.getModifiedScript(changes);
                if (map.getName().equals("ISLAND")) {
                    String old = "  if after_iszara = 0 and CyrusFriend = 0 and HayleStory = 1";
                    if (script.indexOf(old) < 0 || script.indexOf(old) != script.lastIndexOf(old))
                        throw new IllegalStateException("Coyle guard absent or ambiguous");
                    script = script.replace(old, "  if CyrusFriend = 0 and HayleStory = 1");
                }
                Path target = output.resolve("maps").resolve(map.getName() + ".RGM");
                map.writeMap(target.toFile(), script);
                map.readMap(target.toFile());
                String reparsed = map.getScript();
                // Addresses move when instructions change. Compare label identity
                // and every other script token after normalizing those addresses.
                boolean vileAlias = map.getName().equals("VILE");
                if (!canonical(reparsed, vileAlias).equals(canonical(script, vileAlias))) {
                    Files.writeString(output.resolve(map.getName() + ".expected.txt"), canonical(script, vileAlias));
                    Files.writeString(output.resolve(map.getName() + ".actual.txt"), canonical(reparsed, vileAlias));
                    throw new IllegalStateException(map.getName() + ": script compile roundtrip differs");
                }
                if (map.getName().equals("ISLAND") &&
                    (!reparsed.contains("  if CyrusFriend = 0 and HayleStory = 1") ||
                     !reparsed.contains("menuAddItem(\"?hay\", var35, 7)")))
                    throw new IllegalStateException("Coyle topic lost");
                count++;
                System.out.println("Verified " + map.getName());
            }
            if (count != 9) throw new IllegalStateException("Expected nine modified maps: " + count);
        } finally {
            Files.deleteIfExists(changesPath);
        }
    }
}
