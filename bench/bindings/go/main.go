// gosseract harness. Common protocol (see ../README.md): harness TESSDATA LANG PSM PASSES TINY IMG...
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/otiai10/gosseract/v2"
)

func main() {
	a := os.Args[1:]
	td, lang, psm := a[0], a[1], a[2]
	passes, _ := strconv.Atoi(a[3])
	tiny, imgs := a[4], a[5:]
	t := time.Now()
	c := gosseract.NewClient()
	defer c.Close()
	c.SetTessdataPrefix(td)
	c.SetLanguage(lang)
	// PSM "3" = SetPageSegMode before the first Text() (how the API reads);
	// PSM "3var" = SetVariable("tessedit_pageseg_mode", "3"), which gosseract re-applies after its lazy Init.
	if psm != "default" && !strings.HasSuffix(psm, "var") {
		n, _ := strconv.Atoi(psm)
		c.SetPageSegMode(gosseract.PageSegMode(n))
	}
	if strings.HasSuffix(psm, "var") {
		c.SetVariable("tessedit_pageseg_mode", strings.TrimSuffix(psm, "var"))
	}
	ocr := func(p string) string {
		if err := c.SetImage(p); err != nil {
			panic(err)
		}
		s, err := c.Text()
		if err != nil {
			panic(err)
		}
		return s
	}
	ocr(tiny) // gosseract initialises lazily on first Text(): init is part of this call
	init := time.Since(t).Seconds()
	tinyS := []float64{}
	for i := 0; i < 20; i++ {
		t := time.Now()
		ocr(tiny)
		tinyS = append(tinyS, time.Since(t).Seconds())
	}
	texts := []string{}
	for _, p := range imgs {
		texts = append(texts, ocr(p))
	}
	passS := [][]float64{}
	for k := 0; k < passes; k++ {
		row := []float64{}
		for _, p := range imgs {
			t := time.Now()
			ocr(p)
			row = append(row, time.Since(t).Seconds())
		}
		passS = append(passS, row)
	}
	out, _ := json.Marshal(map[string]interface{}{
		"binding": "gosseract", "info": map[string]string{"engine": gosseract.Version(), "note": "init_s = NewClient + first OCR of tiny.png (lazy init)"},
		"init_s": init, "tiny_s": tinyS, "pass_s": passS, "texts": texts})
	fmt.Println(string(out))
}
