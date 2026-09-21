"""Meaningful build checks: offline links, complete source text, release guard."""
import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from pypdf import PdfReader
from build import ROOT, validate, pages_for

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.ids = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs: self.ids.add(attrs["id"])
        for key in ("href", "src"):
            if key in attrs: self.links.append(attrs[key])

data = json.loads((ROOT / "content/course.json").read_text(encoding="utf-8"))
validate(data)
parsers = {}
for file in (ROOT / "site").glob("*.html"):
    parser = Links(); parser.feed(file.read_text(encoding="utf-8")); parsers[file.resolve()] = parser
for file, parser in parsers.items():
    for link in parser.links:
        parts = urlsplit(link)
        assert not parts.scheme and not parts.netloc, f"External dependency: {link}"
        target = (file.parent / unquote(parts.path)).resolve() if parts.path else file
        assert target.is_file(), f"Broken link: {file.name}: {link}"
        if parts.fragment:
            assert parts.fragment in parsers[target].ids, f"Broken anchor: {link}"

mutant = copy.deepcopy(data)
mutant["variants"][0]["progression"] = {}
try:
    validate(mutant)
except ValueError:
    pass
else:
    raise AssertionError("Validator accepted a variant disconnected from practices")
if data["status"] == "template":
    try:
        validate(data, release=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Unfinished template passed student release validation")

manifest = json.loads((ROOT / "site/manifest.json").read_text(encoding="utf-8"))
assert len(manifest["areas"]) >= data["variant_count"] + 2
for name, key, specs in zip(("learning-pages", "subject-areas"), ("lessons", "areas"), pages_for(data)):
    doc = PdfReader(ROOT / f"site/downloads/{name}.pdf")
    assert len(doc.pages) == len(manifest[key]), f"Page manifest mismatch: {name}"
    texts = []
    for page in doc.pages:
        assert abs(float(page.mediabox.width) - 841.89) < 1 and abs(float(page.mediabox.height) - 595.28) < 1, "PDF must use A4 landscape"
        text = page.extract_text()
        assert text and len(text.strip()) > 80, "Empty PDF page"
        assert '\ufffd' not in text, "Broken character encoding"
        texts.append(text)
    compact = re.sub(r"\s+", "", ''.join(texts))
    for spec in specs:
        assert re.sub(r"\s+", "", spec["title"]) in compact, f"Missing PDF heading: {spec['title']}"
        for block in spec["blocks"]:
            # Every source line must survive PDF export; wrapping and indentation may differ.
            for line in block["text"].splitlines():
                if line.strip():
                    assert re.sub(r"\s+", "", line) in compact, f"Missing PDF content: {name}: {line[:60]}"
print(f"PASS: {len(parsers)} offline pages, links/anchors, variant progression, release guard; both PDFs: landscape, text completeness, page count")
