"""Check one complete kit and prevent duplicate outputs from returning."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
from pypdf import PdfReader
from build import ROOT, load_course, validate

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs: self.ids.add(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])

data=load_course(); validate(data)
site=ROOT/'site'
parsers={}
for file in site.glob('*.html'):
    p=Links(); p.feed(file.read_text(encoding='utf-8')); parsers[file.resolve()]=p
for file,p in parsers.items():
    for link in p.links:
        part=urlsplit(link)
        assert not part.scheme and not part.netloc, link
        target=(file.parent/unquote(part.path)).resolve() if part.path else file
        assert target.is_file(),link
        if part.fragment:assert part.fragment in parsers[target].ids,link
expected={'assignment.pdf','guide.pdf','CrystalCounter.cs'}
assert {p.name for p in (site/'downloads').iterdir()}==expected,'Unexpected duplicate output'
assert {p.name for p in (ROOT/'content').glob('*.json')}=={'course.json'},'Multiple content sources'
code_parts=[b['text'] for p in data['guide'] for b in p['blocks'] if b.get('kind')=='code']
assert '\n'.join(code_parts).strip()==data['code'].strip(),'Incomplete or repeated code ranges'
assert (site/'downloads/CrystalCounter.cs').read_text(encoding='utf-8')==data['code']
manifest=json.loads((site/'manifest.json').read_text(encoding='utf-8'))
for name,specs in [('assignment',data['assignment']+data['areas']),('guide',data['guide'])]:
    doc=PdfReader(site/f'downloads/{name}.pdf')
    assert len(doc.pages)==len(manifest[name])
    text=''.join(p.extract_text() for p in doc.pages)
    compact=re.sub(r'\s+','',text)
    for page in doc.pages:
        assert abs(float(page.mediabox.width)-841.89)<1 and abs(float(page.mediabox.height)-595.28)<1
    for spec in specs:
        for block in spec['blocks']:
            for line in block['text'].splitlines():
                if line.strip():assert re.sub(r'\s+','',line) in compact,line[:80]
for old in ['example.html','example-guide.html','example-result.html']:
    text=(site/old).read_text(encoding='utf-8')
    assert 'http-equiv="refresh"' in text and '<article' not in text
try:validate(data,release=True)
except ValueError:assert data['meta']['status']!='ready'
else:assert data['meta']['status']=='ready'
print('PASS: one source, two PDFs, complete code, offline links, PDF text, landscape layout, content-free redirects')
