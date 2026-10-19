import sys, json
sys.path.insert(0, r'e:\works\Aidev\Kbitai绝对安全\kbitai_com_cn\aitools\acmcp\archilinkai\src')
from archilinkai import instance_manager
from archilinkai.tapir_adapter import adapter
from archilinkai.query_engine import engine, QueryRequest
instance_manager.manager.discover_instances()
INST = [i.instance_id for i in instance_manager.manager.list_instances()][0]

# 获取楼梯元素
page = engine.query(QueryRequest(element_type='Stair', limit=5))
stairs = page.items
guids = [s['guid'] for s in stairs]
elems = [{'elementId': {'guid': g}} for g in guids]

# 试试 GetGDLParameters
try:
    r = adapter.execute('GetGDLParameters', {'elements': elems}, INST)
    print('GetGDLParameters:', json.dumps(r, ensure_ascii=False, indent=2)[:2000])
except Exception as e:
    print('err:', e)
