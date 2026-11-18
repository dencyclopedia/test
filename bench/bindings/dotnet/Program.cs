// Tesseract (.NET, NuGet "Tesseract") harness. Common protocol (see ../README.md):
//   dotnet run -- TESSDATA LANG PSM PASSES TINY IMG...
using System.Diagnostics;
using System.Text.Json;
using Tesseract;

var td = args[0]; var lang = args[1]; var psm = args[2]; var passes = int.Parse(args[3]); var tiny = args[4];
var imgs = args.Skip(5).ToArray();
var sw = Stopwatch.StartNew();
using var engine = new TesseractEngine(td, lang, EngineMode.Default);
var initS = sw.Elapsed.TotalSeconds;
string Ocr(string p)
{
    using var img = Pix.LoadFromFile(p);
    using var page = psm == "default" ? engine.Process(img) : engine.Process(img, (PageSegMode)int.Parse(psm));
    return page.GetText();
}
Ocr(tiny);
var tinyS = new List<double>();
for (int i = 0; i < 20; i++) { sw.Restart(); Ocr(tiny); tinyS.Add(sw.Elapsed.TotalSeconds); }
var texts = imgs.Select(Ocr).ToList();
var passS = new List<List<double>>();
for (int k = 0; k < passes; k++)
{
    var row = new List<double>();
    foreach (var p in imgs) { sw.Restart(); Ocr(p); row.Add(sw.Elapsed.TotalSeconds); }
    passS.Add(row);
}
Console.WriteLine(JsonSerializer.Serialize(new Dictionary<string, object> {
    ["binding"] = "dotnet-tesseract",
    ["info"] = new Dictionary<string, string> { ["engine"] = engine.Version, ["default_psm"] = engine.DefaultPageSegMode.ToString(),
        ["package"] = typeof(TesseractEngine).Assembly.GetName().Version.ToString() },
    ["init_s"] = initS, ["tiny_s"] = tinyS, ["pass_s"] = passS, ["texts"] = texts }));
