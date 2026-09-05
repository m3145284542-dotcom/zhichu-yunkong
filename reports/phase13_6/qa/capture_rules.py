"""Capture only the official documents already inspected online."""
import urllib.request,re,hashlib,json
from pathlib import Path
Q=Path(__file__).resolve().parent; root=Q.parents[2]
url='https://www.aicomp.cn/notice/notice-3/4702.html'
page=urllib.request.urlopen(url,timeout=30).read()
(Q/'official_notice.html').write_bytes(page)
links=re.findall(r'href=["\']([^"\']+\.pdf)["\']',page.decode('utf-8'))
from urllib.parse import unquote,quote
records=[]
for link in links:
    decoded=unquote(link)
    if '科技创新组' not in decoded:continue
    link=quote(link,safe=':/%')
    kind='template' if '大纲' in decoded else 'requirements'
    data=urllib.request.urlopen(link,timeout=30).read()
    path=Q/f'official_{kind}.pdf';path.write_bytes(data)
    records.append({'url':link,'file':path.name,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)})
(Q/'official_rules_manifest.json').write_text(json.dumps({'retrieved':'2026-09-05','notice':url,'general_rules':'https://www.aicomp.cn/bylaws','attachments':records},ensure_ascii=False,indent=2),encoding='utf-8')
print(len(records))
