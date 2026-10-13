"""Quality gate: the Python part of Aider's polyglot benchmark as hidden-test tasks.

Reads a checkout of https://github.com/Aider-AI/polyglot-benchmark and writes tasks in the
`export_tasks` schema, so both arms (RIFT `BENCH_SET=file`, Claude Code `run_claude.py`) run them.
The agent sees the instructions and the stub only; the exercise's tests stay hidden and judge the
final tree. `--check` proves each task is real (hidden tests fail on the stub) and achievable (they
pass with the exercise's example solution) in the same network-less container.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse, json, sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_claude import accept  # noqa: E402

PROMPT = """{instructions}

Use the instructions above to complete {files}. Keep the existing function and class names: \
tests you cannot see import them. Use only the Python standard library."""


def task(ex):
    meta = json.loads((ex / '.meta/config.json').read_text())['files']
    docs = [ex / '.docs/instructions.md', ex / '.docs/instructions.append.md']
    instructions = '\n\n'.join(p.read_text().strip() for p in docs if p.exists())
    solution, tests, example = meta['solution'], meta['test'], meta['example']
    assert len(solution) == 1 and len(example) == 1, ex.name
    modules = ' '.join(t.removesuffix('.py') for t in tests if t.endswith('_test.py'))
    return {
        'set': 'polyglot-py', 'id': 'py_' + ex.name.replace('-', '_'), 'held_out': True,
        'request': PROMPT.format(instructions=instructions, files=' and '.join(f'`{s}`' for s in solution)),
        'allow_exec': True, 'node': False,
        'files': [[s, (ex / s).read_text()] for s in solution],
        'reference': [[solution[0], (ex / example[0]).read_text()]],
        'hidden': [[t, (ex / t).read_text()] for t in tests],
        'concurrent_edit': None,
        'acceptance': {'image': 'python:3.13-alpine',
                       'command': f'PYTHONDONTWRITEBYTECODE=1 python -m unittest -v {modules}'},
    }


def check(t):
    as_bytes = lambda files: [(p, c.encode()) for p, c in files]
    stub_ok, _ = accept(t, as_bytes(t['files']))
    ref_ok, ref_out = accept(t, as_bytes(t['reference']))
    return t['id'], stub_ok, ref_ok, ref_out[-300:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('checkout', help='polyglot-benchmark checkout')
    ap.add_argument('--out', default=Path(__file__).resolve().parent.parent / 'tasks' / 'polyglot-py.json')
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    root = Path(args.checkout) / 'python/exercises/practice'
    tasks = [task(ex) for ex in sorted(root.iterdir()) if ex.is_dir()]
    if args.check:
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(check, tasks))
        bad = {i for i, stub_ok, ref_ok, _ in results if stub_ok or not ref_ok}
        for i, stub_ok, ref_ok, out in results:
            if i in bad:
                print(f'UNSOUND {i}: stub passes={stub_ok} reference passes={ref_ok}\n{out}', file=sys.stderr)
        tasks = [t for t in tasks if t['id'] not in bad]
    Path(args.out).write_text(json.dumps(tasks, indent=1) + '\n')
    print(f'{len(tasks)} tasks -> {args.out}')


if __name__ == '__main__':
    main()
