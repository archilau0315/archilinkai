import sys, json
sys.path.insert(0, r'e:\works\Aidev\Kbitai绝对安全\kbitai_com_cn\aitools\acmcp\archilinkai\src')
from archilinkai import instance_manager
from archilinkai.code_review_service import run_review
instance_manager.manager.discover_instances()
INST = [i.instance_id for i in instance_manager.manager.list_instances()][0]

r = run_review(rules=['openings', 'headroom', 'stair_width', 'stair_tread'],
               instance=INST)
print('per_rule:', r['per_rule'])
for rule in ('openings', 'headroom', 'stair_width', 'stair_tread'):
    vs = r['violations'].get(rule, [])
    print(f'--- {rule}: {len(vs)} 条')
    for v in vs[:2]:
        print('   ', v.get('message'))
