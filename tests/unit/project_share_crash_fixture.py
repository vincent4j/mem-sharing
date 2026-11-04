"""项目共享硬崩溃合成 fixture：子进程在指定事务阶段 os._exit 硬退出。

由 tests/unit/test_project_share_runtime.py 以子进程方式启动，绝不接触真实
HOME 或真实项目；项目 Git 主 checkout 与 HOME 均由调用方在临时目录合成。
崩溃规格 JSON：{"home", "project", "event", "path_suffix", "occurrence",
"exit_code"}；hook 在第 occurrence 次匹配 (event, path 以 path_suffix 结尾)
时调用 os._exit 硬退出——不经异常回滚、不执行 finally、不释放锁。若崩溃点
未触发，本进程以退出码 3 结束并说明，便于测试识别规格错误。
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from agm_core import project_share as ps  # noqa: E402

ZH = '- 提交信息使用中文。\n'
TESTS = '- 修改后运行测试。\n'
AGENTS_TEXT = '# 约定\n\n' + ZH + '\n# 其他\n\n- 仅用标准库。\n'
CLAUDE_TEXT = '# 约定\n\n' + ZH + TESTS + '- 表达简洁，先给结论。\n'
WB_TEXT = '# 约定\n\n' + ZH + TESTS + '- 只走海运。\n'


def build_proposal(request):
    preview = ps.plan_share(dict(request))
    if preview['status'] != 'completed':
        raise SystemExit('preview failed: ' + json.dumps(preview['errors'],
                                                         ensure_ascii=False))

    def seg(name, text):
        match = [s for s in preview['segments']
                 if s['source'] == name and s['text'] == text]
        if not match:
            raise SystemExit('segment missing: ' + name)
        return match[0]

    return {'schema_version': 1, 'basis': preview['basis'], 'groups': [
        {'summary': 'AGENTS 已有中文提交要求，默认整理重复', 'same_content': True,
         'items': [{'file': f, 'start': seg(f, ZH)['start'], 'end': seg(f, ZH)['end']}
                   for f in ('claude', 'workbuddy')]},
        {'summary': '两份独立文件都要求修改后运行测试', 'same_content': True,
         'items': [{'file': f, 'start': seg(f, TESTS)['start'], 'end': seg(f, TESTS)['end']}
                   for f in ('claude', 'workbuddy')]},
    ]}


def main(argv):
    if len(argv) != 2:
        return 3
    spec = json.loads(Path(argv[1]).read_text())
    request = {'home': spec['home'], 'project': spec['project']}
    proposal = build_proposal(request)
    result = ps.plan_share(dict(request, proposal=proposal, selection='共享 1、2'))
    if result['status'] != 'approval_required':
        print(json.dumps(result, ensure_ascii=False))
        return 3
    plan = result['approval_plan']
    seen = {'n': 0}

    def crash_hook(event, path):
        if event != spec['event'] or not str(path).endswith(spec['path_suffix']):
            return
        seen['n'] += 1
        if seen['n'] >= spec['occurrence']:
            sys.stdout.flush()
            os._exit(spec.get('exit_code', 9))  # 硬退出：无异常回滚、无 finally

    outcome = ps.execute_share(
        plan, dict(plan, confirmed_at='2026-11-03T15:40:00Z',
                   reference='synthetic crash fixture confirmation'),
        request=request, hook=crash_hook)
    # 正常返回即崩溃点未触发：报告并退出 3，父测试据此判定规格错误。
    print(json.dumps({'crashed': False, 'status': outcome['status'],
                      'matches': seen['n']}, ensure_ascii=False))
    return 3


if __name__ == '__main__':
    sys.exit(main(sys.argv))
