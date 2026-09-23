import json
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

assert Path('/.dockerenv').exists(), 'Запускайте в Docker'
repo=Path(__file__).resolve().parents[3]
root=Path(sys.argv[1])
root.mkdir(parents=True,exist_ok=False)
old_jar=Path(sys.argv[2]).resolve(strict=True)
subprocess.run(['java',str(Path(__file__).with_name('generate_vector_logo.java')),str(repo/'docs/ruleway_design/ruleway-icon.svg'),str(root)],check=True)
sprite=(root/'ruleway_vector_logo.iuml').read_text()
example=repo/'examples/basic_regulation_no_lanes.puml'
expanded=subprocess.run(['plantuml','-charset','UTF-8','-pipe','-filename',example.name,'-preproc'],input=example.read_bytes(),cwd=example.parent,capture_output=True,check=True)
source=expanded.stdout.decode('utf-8')
# После приёмки публичные компоненты уже содержат знак и совместимое условие.
assert len(re.findall(r'^sprite ruleway_logo ',source,re.M)) == 1
assert 'data:image' not in source
(root/'wiki_vector_logo.puml').write_text(source)
style=re.search(r'<style>.*?</style>',source,re.S).group(0)
probe='@startuml\n'+sprite+style+'\nleft header\n<size:13><$ruleway_logo></size>\nendheader\ntitle Проверка знака\nstart\nstop\n@enduml\n'
(root/'icon_probe.puml').write_text(probe)
report={}
for version,jar in [('1.2025.10',str(old_jar)),('1.2026.5','/opt/plantuml/plantuml.jar')]:
    version_text=subprocess.run(['java','-jar',jar,'-version'],capture_output=True,text=True,check=True).stdout
    assert ('PlantUML version '+version+' ') in version_text, version_text
    folder=root/version
    folder.mkdir(exist_ok=True)
    for name in ['wiki_vector_logo','icon_probe']:
        (folder/(name+'.puml')).write_text((root/(name+'.puml')).read_text())
    for fmt in ['svg','png']:
        result=subprocess.run(['java','-Djava.awt.headless=true','-jar',jar,'--format',fmt,str(folder/'wiki_vector_logo.puml'),str(folder/'icon_probe.puml')],capture_output=True,text=True)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
    report[version]={}
    for name in ['wiki_vector_logo','icon_probe']:
        path=folder/(name+'.svg')
        xml=ET.parse(path).getroot()
        ns='{http://www.w3.org/2000/svg}'
        texts=''.join(xml.itertext())
        assert '<center>' not in texts and '<left>' not in texts
        assert not list(xml.iter(ns+'image'))
        assert 'data:image' not in path.read_text()
        assert len(list(xml.iter(ns+'path')))>=134
        report[version][name]={'paths':len(list(xml.iter(ns+'path'))),'images':0,'viewBox':xml.get('viewBox')}
        print(version,name,report[version][name],flush=True)
(root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
