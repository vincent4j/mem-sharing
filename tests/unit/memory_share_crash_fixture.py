"""Only this test process can terminate at an injected Transaction hook."""
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import memory_share as ms
approval = json.loads(Path(sys.argv[1]).read_text())
plan = {k: v for k, v in approval.items() if k not in ('confirmed_at', 'reference')}
def crash(event, path):
    if event == 'after_write' and path.name == ms.TOPIC_NAME:
        os._exit(70)
result = ms.execute_share(plan, approval, hook=crash)
print(json.dumps(result))
sys.exit(2)
