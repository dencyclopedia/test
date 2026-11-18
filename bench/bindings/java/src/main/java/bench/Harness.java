// Tess4J harness. Common protocol (see ../README.md): Harness TESSDATA LANG PSM PASSES TINY IMG...
package bench;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import net.sourceforge.tess4j.Tesseract;

public class Harness {
  static String esc(String s) {
    StringBuilder b = new StringBuilder();
    for (char c : s.toCharArray()) {
      if (c == '"') b.append("\\\""); else if (c == '\\') b.append("\\\\"); else if (c == '\n') b.append("\\n");
      else if (c < 0x20) b.append(String.format("\\u%04x", (int) c)); else b.append(c);
    }
    return b.toString();
  }
  public static void main(String[] a) throws Exception {
    String td = a[0], lang = a[1], psm = a[2]; int passes = Integer.parseInt(a[3]); String tiny = a[4];
    List<String> imgs = new ArrayList<>(); for (int i = 5; i < a.length; i++) imgs.add(a[i]);
    long t0 = System.nanoTime();
    Tesseract t = new Tesseract();
    t.setDatapath(td); t.setLanguage(lang);
    if (!psm.equals("default")) t.setPageSegMode(Integer.parseInt(psm));
    String first = t.doOCR(new File(tiny));
    double init = (System.nanoTime() - t0) / 1e9;
    StringBuilder tinyS = new StringBuilder();
    for (int i = 0; i < 20; i++) { long s = System.nanoTime(); t.doOCR(new File(tiny)); tinyS.append(i > 0 ? "," : "").append((System.nanoTime() - s) / 1e9); }
    StringBuilder texts = new StringBuilder();
    for (int i = 0; i < imgs.size(); i++) texts.append(i > 0 ? "," : "").append('"').append(esc(t.doOCR(new File(imgs.get(i))))).append('"');
    StringBuilder pass = new StringBuilder();
    for (int k = 0; k < passes; k++) {
      pass.append(k > 0 ? "," : "").append('[');
      for (int i = 0; i < imgs.size(); i++) { long s = System.nanoTime(); t.doOCR(new File(imgs.get(i))); pass.append(i > 0 ? "," : "").append((System.nanoTime() - s) / 1e9); }
      pass.append(']');
    }
    System.out.println("{\"binding\":\"tess4j\",\"info\":{\"engine\":\"system libtesseract via JNA\",\"note\":\"Tess4J doOCR(File) re-initialises the engine on every call; init_s = new Tesseract() + first doOCR(tiny)\"},"
        + "\"init_s\":" + init + ",\"tiny_s\":[" + tinyS + "],\"pass_s\":[" + pass + "],\"texts\":[" + texts + "]}");
  }
}
