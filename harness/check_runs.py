"""Check that the counted runs have no infrastructure error in either agent (writes results/integrity.txt).

For every official and ablation run in runs/:
  - every record finished: no runner error, and the run ended on its own (not stopped by us). A run
    whose cost could not be fully measured still counts, since each instance gets one finished run;
    its cost is a lower bound and the count is reported (cost is never a guess);
  - every SWE-bench record has a verdict from the official harness (resolved, not resolved, an empty
    patch or a patch the harness could not apply), its instance's gold patch was graded with a harness
    report (an instance whose gold patch fails is left out for every agent, and listed), and the
    harness's own report (or, for a patch it could not apply, its log) is in grading/;
And for the official comparison:
  - both agents ran exactly the same tasks, the same number of times, in every task set.

An agent's own end state (Forge's SUCCEEDED / UNVERIFIED / FAILED, Claude Code's success) is its claim
about its work, not a result: acceptance is decided by the hidden tests alone. A task an agent did not
solve is a result, not an error. Exits 1 if anything fails.
"""
from pathlib import Path
import collections, json, sys

ROOT = Path(__file__).resolve().parent.parent
GRADED = {'resolved', 'not resolved', 'empty patch', 'patch does not apply'}


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
        bad, left_out = [], set()
        gpath = d / 'grading' / 'gold-validity.json'
        gold = json.loads(gpath.read_text()) if gpath.exists() else {}
        for r in rs:
            where = f"{d.name} {r['task']} rep {r.get('rep')}"
            if r.get('error') or r.get('is_error'):
                bad.append(f'{where}: runner error {r.get("error")!r}')
            # A counted run ended on its own. One whose cost could not be fully measured still counts
            # (one finished run per instance); its cost is a lower bound, and the count is reported.
            # Reaching its own deadline is how a run ends, and counts against it; a run cut off by the
            # provider, or still running when stopped, did not finish.
            if r.get('state') == 'RUNNING' or (r.get('state') == 'INTERRUPTED' and 'deadline' not in str(r.get('reason'))):
                bad.append(f'{where}: stopped before it finished ({r.get("state")}: {r.get("reason")})')
            if 'gold_valid' in r or r.get('set', '').startswith('swe'):
                if r.get('grade_detail') not in GRADED:
                    bad.append(f'{where}: no verdict from the SWE-bench harness ({r.get("grade_detail")!r})')
                if not r.get('gold_valid'):
                    # An instance whose gold patch fails is left out for every agent, but only on the
                    # harness's own report: a gold run without one is a harness error, not an invalid instance.
                    if not (gold.get(r['task']) or {}).get('report'):
                        bad.append(f'{where}: no harness report shows that the gold patch does not resolve here')
                    left_out.add(r['task'])
                if r.get('grade_detail') in ('resolved', 'not resolved') and not (d / 'grading' / 'reports' / f"{r['task']}.json").exists():
                    bad.append(f'{where}: the harness report is missing from grading/')
                if r.get('grade_detail') == 'patch does not apply' and not (d / 'grading' / 'reports' / f"{r['task']}.patch-apply-failed.log").exists():
                    bad.append(f'{where}: the harness log of the patch it could not apply is missing from grading/')
            if info['kind'] == 'official':
                plan[r.get('set')][info['agent']][r['task']] += 1
        problems += bad
        states = collections.Counter(str(r.get('state')) for r in rs)
        partial = sum(r.get('usage_complete') is False for r in rs)
        lines.append(f"{d.name}: {len(rs)} runs, {len(bad)} problems; agent end states {dict(sorted(states.items()))}"
                     + (f'; {partial} with incomplete usage (cost a lower bound)' if partial else '')
                     + (f"; left out for every agent (gold patch does not resolve here): {', '.join(sorted(left_out))}" if left_out else ''))
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
