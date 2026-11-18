#!/usr/bin/env python3
"""Fetch the public-domain source texts and the OFL fonts the corpus is rendered from.

Texts: extracted passages are written to corpus/texts/ and committed, so rendering does
not need the network. Fonts: downloaded into corpus/gen/.cache/fonts/ (git-ignored) and
checked against the sha256 recorded below.

Usage: python3 corpus/gen/fetch_sources.py [--texts] [--fonts]   (default: both)
"""
import hashlib, io, json, re, sys, urllib.request, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXTS = HERE.parent / "texts"
CACHE = HERE / ".cache"

GUTENBERG = {
    # id: (mirror url, title, author, opening words of the first paragraph to use)
    "austen": ("https://gutenberg.pglaf.org/1/3/4/1342/1342-0.txt", "Pride and Prejudice", "Jane Austen", "It is a truth universally acknowledged"),
    "doyle": ("https://gutenberg.pglaf.org/1/6/6/1661/1661-0.txt", "The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "To Sherlock Holmes she is always"),
    "shelley": ("https://gutenberg.pglaf.org/8/84/84-0.txt", "Frankenstein", "Mary Wollstonecraft Shelley", "Six years have passed since I resolved"),
    "carroll": ("https://gutenberg.pglaf.org/1/11/11-0.txt", "Alice's Adventures in Wonderland", "Lewis Carroll", "Alice was beginning to get very tired"),
}
UDHR_ZIP = "https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/udhr2.zip"
UDHR_FILES = {  # tesseract lang code -> file in udhr2.zip
    "eng": "eng.txt", "deu": "deu.txt", "fra": "fra.txt", "spa": "spa.txt", "por": "por_PT.txt",
    "ita": "ita.txt", "rus": "rus.txt", "chi_sim": "cmn_hans.txt", "jpn": "jpn.txt", "kor": "kor.txt",
    "ara": "arb.txt", "hin": "hin.txt", "vie": "vie.txt", "uzb": "uzn_latn.txt",
}
CJK = {"chi_sim", "jpn"}

GFONTS_COMMIT = "7af0d90b4d532ffa4b041937b560c6df4e7b1e95"  # github.com/google/fonts, pinned
FONTS = {
    "NotoSansSC[wght].ttf": ("ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf", "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"),
    "NotoSansKR[wght].ttf": ("ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf", "194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252"),
    "NotoNaskhArabic[wght].ttf": ("ofl/notonaskharabic/NotoNaskhArabic%5Bwght%5D.ttf", "67b5a525a661b607971fbd3f96a81b89d3a768e74534fca84f18ac97e6fab72f"),
    "NotoSansDevanagari[wdth,wght].ttf": ("ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth,wght%5D.ttf", "14ec4af41f27482216d1c2229f417ff9b1425e1babb014e57d1d40d03229853e"),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ocr-test-lab-corpus/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def clean(s):
    s = s.replace("_", "")           # Gutenberg italics markers
    s = s.replace("‐", "-")     # UDHR files use U+2010 HYPHEN; render/compare as ASCII hyphen
    return re.sub(r"\s+", " ", s).strip()


def take_sentences(paras, budget):
    """Whole sentences, paragraph structure kept, until `budget` characters are reached."""
    out, n = [], 0
    for p in paras:
        sents = re.split(r"(?<=[.!?”;])\s+(?=[“A-Z])", p)
        cur = []
        for s in sents:
            cur.append(s)
            n += len(s) + 1
            if n >= budget:
                out.append(" ".join(cur))
                return out
        out.append(" ".join(cur))
    return out


def fetch_texts():
    TEXTS.mkdir(parents=True, exist_ok=True)
    meta = {"gutenberg": {}, "udhr": {}}
    for key, (url, title, author, opening) in GUTENBERG.items():
        raw = get(url)
        t = raw.decode("utf-8-sig")
        body = t[t.index("\n", t.index("*** START")):t.index("*** END")]
        body = re.sub(r"\[Illustration(?:[^\[\]]|\[[^\]]*\])*\]", "", body)  # drop illustration captions
        paras = [clean(p) for p in re.split(r"\n\s*\n", body)]
        i = next(i for i, p in enumerate(paras) if p.startswith(opening))
        paras = [p for p in paras[i:i + 40] if p and not p.startswith("[")]
        page = take_sentences(paras, 1100)     # 'clean' full page
        half = take_sentences(paras, 520)      # 'degraded' half page
        (TEXTS / f"{key}.page.txt").write_text("\n".join(page) + "\n", encoding="utf-8")
        (TEXTS / f"{key}.half.txt").write_text("\n".join(half) + "\n", encoding="utf-8")
        meta["gutenberg"][key] = {"url": url, "title": title, "author": author,
                                  "sha256": hashlib.sha256(raw).hexdigest(), "starts_with": opening}
    raw = get(UDHR_ZIP)
    z = zipfile.ZipFile(io.BytesIO(raw))
    for lang, fn in UDHR_FILES.items():
        lines = [clean(l) for l in z.read("udhr2/" + fn).decode("utf-8").splitlines()]
        lines = [l for l in lines if l]
        budget = 280 if lang in CJK or lang == "kor" else 650
        pages, idx = [], 0
        for _ in range(2):
            cur, n = [], 0
            while idx < len(lines) and n < budget:
                cur.append(lines[idx]); n += len(lines[idx]); idx += 1
            pages.append(cur)
        for k, p in enumerate(pages, 1):
            (TEXTS / f"udhr_{lang}.p{k}.txt").write_text("\n".join(p) + "\n", encoding="utf-8")
        meta["udhr"][lang] = {"file": "udhr2/" + fn}
    meta["udhr_zip"] = {"url": UDHR_ZIP, "sha256": hashlib.sha256(raw).hexdigest()}
    (TEXTS / "sources.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("texts ->", TEXTS)


def fetch_fonts():
    d = CACHE / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    for name, (path, sha) in FONTS.items():
        f = d / name
        if not f.exists() or hashlib.sha256(f.read_bytes()).hexdigest() != sha:
            data = get(f"https://raw.githubusercontent.com/google/fonts/{GFONTS_COMMIT}/{path}")
            got = hashlib.sha256(data).hexdigest()
            if got != sha:
                sys.exit(f"sha256 mismatch for {name}: {got}")
            f.write_bytes(data)
        print("font ok", name)


if __name__ == "__main__":
    args = set(sys.argv[1:]) or {"--texts", "--fonts"}
    if "--texts" in args:
        fetch_texts()
    if "--fonts" in args:
        fetch_fonts()
