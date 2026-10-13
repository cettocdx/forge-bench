"""Check that the counted runs have no infrastructure error in either agent (writes results/integrity.txt).

For every official and ablation run in runs/:
  - every record finished: no runner error, complete token usage (cost is never a guess);
  - every SWE-bench record has a verdict from the official harness (resolved, not resolved or an empty
    patch), its instance's gold patch resolves here, and the harness's own report is in grading/;
And for the official comparison:
  - both agents ran exactly the same tasks, the same number of times, in every task set.

An agent's own end state (Forge's SUCCEEDED / UNVERIFIED / FAILED, Claude Code's success) is its claim
about its work, not a result: acceptance is decided by the hidden tests alone. A task an agent did not
solve is a result, not an error. Exits 1 if anything fails.
"""
from pathlib import Path
import collections, json, sys

ROOT = Path(__file__).resolve().parent.parent
GRADED = {'resolved', 'not resolved', 'empty patch'}


def records(d):
    out = []
    for line in (d / 'results.jsonl').read_text().splitlines():
        line = line.removeprefix('BENCH ').strip()
        if line:
            r = json.loads(line)
            if 'task' in r:
                out.append(r)
    return out


def main():
    problems, lines, plan = [], [], collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    for d in sorted(p for p in (ROOT / 'runs').iterdir() if p.is_dir()):
        info = json.loads((d / 'run.json').read_text())
        if info['kind'] not in ('official', 'ablation'):
            continue
        rs = records(d)
        bad = []
        for r in rs:
            where = f"{d.name} {r['task']} rep {r.get('rep')}"
            if r.get('error') or r.get('is_error'):
                bad.append(f'{where}: runner error {r.get("error")!r}')
            if r.get('usage_complete') is False:
                bad.append(f'{where}: incomplete usage')
            if 'gold_valid' in r or r.get('set', '').startswith('swe'):
                if r.get('grade_detail') not in GRADED:
                    bad.append(f'{where}: no verdict from the SWE-bench harness ({r.get("grade_detail")!r})')
                if not r.get('gold_valid'):
                    bad.append(f'{where}: the gold patch does not resolve here')
                if r.get('grade_detail') in ('resolved', 'not resolved') and not (d / 'grading' / 'reports' / f"{r['task']}.json").exists():
                    bad.append(f'{where}: the harness report is missing from grading/')
            if info['kind'] == 'official':
                plan[r.get('set')][info['agent']][r['task']] += 1
        problems += bad
        states = collections.Counter(str(r.get('state')) for r in rs)
        lines.append(f"{d.name}: {len(rs)} runs, {len(bad)} problems; agent end states {dict(sorted(states.items()))}")
    for s, agents in sorted(plan.items(), key=lambda kv: str(kv[0])):
        runs = {a: dict(c) for a, c in agents.items()}
        if len(runs) != 2 or len({json.dumps(c, sort_keys=True) for c in runs.values()}) != 1:
            problems.append(f'set {s}: the agents did not run the same tasks the same number of times')
        else:
            c = next(iter(runs.values()))
            lines.append(f"set {s}: both agents ran the same {len(c)} tasks, {sum(c.values())} runs each")
    report = '\n'.join(lines + [''] + (['PROBLEMS:'] + problems if problems else ['No infrastructure error in any counted run of either agent.'])) + '\n'
    (ROOT / 'results' / 'integrity.txt').write_text(report)
    print(report, end='')
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
