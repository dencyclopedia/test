// C++ TessBaseAPI harness. Common protocol (see ../README.md):
//   harness TESSDATA LANG PSM PASSES TINY IMG...   -> JSON on stdout
#include <tesseract/baseapi.h>
#include <leptonica/allheaders.h>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

static double now() { return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static std::string esc(const char* s) {
  std::string o;
  for (const char* p = s; *p; ++p) {
    unsigned char c = *p;
    if (c == '"') o += "\\\""; else if (c == '\\') o += "\\\\"; else if (c == '\n') o += "\\n";
    else if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o += b; } else o += (char)c;
  }
  return o;
}
int main(int argc, char** argv) {
  const char* td = argv[1]; const char* lang = argv[2]; std::string psm = argv[3]; int passes = atoi(argv[4]);
  const char* tiny = argv[5]; std::vector<const char*> imgs(argv + 6, argv + argc);
  double t = now();
  auto* api = new tesseract::TessBaseAPI();
  if (api->Init(td, lang)) { fprintf(stderr, "Could not initialize tesseract.\n"); return 1; }
  int default_psm = api->GetPageSegMode();
  if (psm != "default") api->SetPageSegMode((tesseract::PageSegMode)atoi(psm.c_str()));
  double init_s = now() - t;
  auto ocr = [&](const char* p) {
    Pix* pix = pixRead(p); api->SetImage(pix); char* txt = api->GetUTF8Text();
    std::string s(txt); delete[] txt; pixDestroy(&pix); return s;
  };
  ocr(tiny);
  std::string tiny_s;
  for (int i = 0; i < 20; i++) { double a = now(); ocr(tiny); tiny_s += (i ? "," : "") + std::to_string(now() - a); }
  std::string texts;
  for (size_t i = 0; i < imgs.size(); i++) texts += std::string(i ? "," : "") + "\"" + esc(ocr(imgs[i]).c_str()) + "\"";
  std::string pass_s;
  for (int k = 0; k < passes; k++) {
    pass_s += std::string(k ? "," : "") + "[";
    for (size_t i = 0; i < imgs.size(); i++) { double a = now(); ocr(imgs[i]); pass_s += (i ? "," : "") + std::to_string(now() - a); }
    pass_s += "]";
  }
  printf("{\"binding\":\"cpp-tessbaseapi\",\"info\":{\"engine\":\"%s\",\"default_psm\":\"%d\"},\"init_s\":%f,\"tiny_s\":[%s],\"pass_s\":[%s],\"texts\":[%s]}\n",
         esc(api->Version()).c_str(), default_psm, init_s, tiny_s.c_str(), pass_s.c_str(), texts.c_str());
  api->End(); delete api;
  return 0;
}
