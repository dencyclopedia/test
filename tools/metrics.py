"""Shared OCR accuracy metrics. See LAB.md for the normalisation rules."""
import unicodedata


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def _lev(a, b) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(truth: str, hyp: str) -> float:
    t, h = normalize(truth), normalize(hyp)
    return _lev(t, h) / max(len(t), 1)


def wer(truth: str, hyp: str) -> float:
    t, h = normalize(truth).split(" "), normalize(hyp).split(" ")
    return _lev(t, h) / max(len(t), 1)


if __name__ == "__main__":
    assert cer("hello world", "hello world") == 0
    assert abs(cer("abcd", "abce") - 0.25) < 1e-9
    assert abs(wer("a b c d", "a b x d") - 0.25) < 1e-9
    print("ok")
