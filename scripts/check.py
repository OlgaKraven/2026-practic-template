"""Meaningful build checks: offline links, complete source text, release guard."""
import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from build import ROOT, validate

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

for file in (ROOT / "site/downloads").glob("*.pdf"):
    assert file.stat().st_size > 10000, f"Empty PDF: {file.name}"
manifest = json.loads((ROOT / "site/manifest.json").read_text(encoding="utf-8"))
assert len(manifest["areas"]) >= data["variant_count"] + 2
print(f"PASS: {len(parsers)} offline pages, all links/anchors, variant progression, release guard, PDF outputs")
