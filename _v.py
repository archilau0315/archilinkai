import sys, json
sys.path.insert(0, r'e:\works\Aidev\Kbitai绝对安全\kbitai_com_cn\aitools\acmcp\archilinkai\src')
from archilinkai import instance_manager
from archilinkai import material_report
instance_manager.manager.discover_instances()
INST = [i.instance_id for i in instance_manager.manager.list_instances()][0]

report = material_report.generate_material_report(instance=INST)
print('summary:', report['summary'])
print('by_type keys:', list(report['by_type'].keys()))
print('details count:', len(report['details']))
if report['details']:
    print('first detail:', report['details'][0])
