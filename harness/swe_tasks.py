"""SWE-bench sets (Lite, the benchmark Aider reported on; Verified's hard instances): selection,
repositories, patches, grading.

  select   a seeded random sample of a SWE-bench dataset (fixed before any agent ran) -> tasks/swe-lite.json
           --dataset SWE-bench/SWE-bench_Verified --difficulty "1-4 hours" ">4 hours" picks the instances
           SWE-bench's annotators estimated take an engineer an hour or more
  prepare  each task's repository at its base commit, without .git, under --repos DIR/<instance_id>
  patch    the git diff between a prepared repository and an agent's final tree
  evaluate official SWE-bench harness over every agent's patches and the gold patch, one instance at a time

Grading uses the official harness and its published evaluation images: the instance's tests run in
the instance's own environment after the agent's patch and the hidden test patch are applied.
Instances whose gold patch does not pass in that harness here are dropped before any agent runs.
"""
from pathlib import Path
import argparse, json, random, re, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parent.parent
DATASET = 'SWE-bench/SWE-bench_Lite'
SEED, N = 20261013, 20
# swebench.harness.constants.APPLY_PATCH_FAIL: the harness's log line for a patch it could not apply.
APPLY_PATCH_FAIL = '>>>>> Patch Apply Failed'

PROMPT = """Resolve the following GitHub issue in this repository ({repo}).

<issue>
{problem}
</issue>

The repository is checked out in the current folder at the commit where the issue was reported. Fix the \
issue by changing the library's source code. Do not edit or add tests: hidden tests will check the fix."""


# No background maintenance, fsmonitor or auto-gc: a temporary repository must be quiet when it is removed.
GIT_QUIET = ['-c', 'maintenance.auto=false', '-c', 'gc.auto=0', '-c', 'core.fsmonitor=false', '-c', 'core.untrackedCache=false']


def sh(*cmd, cwd=None):
    if cmd[0] == 'git':
        cmd = ('git', *GIT_QUIET, *cmd[1:])
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def load(dataset=DATASET):
    from datasets import load_dataset
    return {r['instance_id']: r for r in load_dataset(dataset, split='test')}


def select(args):
    rows = load(args.dataset)
    exclude = set()
    for f in args.exclude or []:
        exclude |= {t['id'] for t in json.loads(Path(f).read_text())}
    pool = sorted(i for i in rows if i not in exclude and (not args.difficulty or rows[i].get('difficulty') in args.difficulty))
    ids = random.Random(args.seed).sample(pool, args.n)
    tasks = []
    for i in sorted(ids):
        r = rows[i]
        tasks.append({
            'set': args.set_name, 'id': i, 'held_out': True,
            'request': PROMPT.format(repo=r['repo'], problem=r['problem_statement'].strip()),
            'allow_exec': True, 'node': False, 'files': [], 'reference': [], 'hidden': [], 'concurrent_edit': None,
            'acceptance': {'image': 'swebench', 'command': f'{args.dataset} {i}'},
            'swe': {'repo': r['repo'], 'base_commit': r['base_commit'], 'version': r['version'],
                    **({'difficulty': r['difficulty']} if r.get('difficulty') else {})},
        })
    out = Path(args.out)
    out.write_text(json.dumps(tasks, indent=1) + '\n')
    print(f'{len(tasks)} tasks (seed {args.seed}, {args.n} of {len(pool)}) -> {out}')


def prepare(args):
    repos = Path(args.repos)
    for t in json.loads(Path(args.tasks).read_text()):
        d = repos / t['id']
        if (d / '.prepared').exists():
            continue
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        sh('git', 'init', '-q', cwd=d)
        sh('git', 'fetch', '-q', '--depth', '1', f"https://github.com/{t['swe']['repo']}.git", t['swe']['base_commit'], cwd=d)
        sh('git', 'checkout', '-q', 'FETCH_HEAD', cwd=d)
        shutil.rmtree(d / '.git')
        (d / '.prepared').write_text(t['swe']['base_commit'] + '\n')
        print('prepared', t['id'], flush=True)


# Left out of every patch, for both agents: run artefacts, not changes (bytecode, caches, metadata).
JUNK = shutil.ignore_patterns('.prepared', '.git', '.claude', '__pycache__', '*.pyc', '*.pyo', '.pytest_cache',
                              '.mypy_cache', '.hypothesis', '*.egg-info', '.tox', '.venv', '.rift-tmp-*')


def make_patch(base: Path, final: Path) -> str:
    """git diff from the prepared repository to an agent's final tree (both without .git). Both trees
    are copied the same way (symlinks kept as links, run artefacts left out), so only real edits show."""
    with tempfile.TemporaryDirectory(prefix='swe-patch-', ignore_cleanup_errors=True) as w:
        w = Path(w) / 'repo'
        shutil.copytree(base, w, symlinks=True, ignore=JUNK)
        sh('git', 'init', '-q', cwd=w)
        sh('git', '-c', 'core.autocrlf=false', 'add', '-A', '-f', cwd=w)
        sh('git', '-c', 'user.name=bench', '-c', 'user.email=bench@localhost', 'commit', '-q', '-m', 'base', cwd=w)
        for p in list(w.iterdir()):
            if p.name != '.git':
                shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()
        ignored = JUNK(str(final), [p.name for p in final.iterdir()])
        for p in final.iterdir():
            if p.name in ignored:
                continue
            dst = w / p.name
            shutil.copytree(p, dst, symlinks=True, ignore=JUNK) if p.is_dir() and not p.is_symlink() else shutil.copy2(p, dst, follow_symlinks=False)
        sh('git', 'add', '-A', '-f', cwd=w)
        return sh('git', '-c', 'core.quotepath=false', 'diff', '--cached', '--binary', cwd=w)


def patch_from_changes(base: Path, changes) -> str:
    """Forge records the files its run changed; the patch is made the same way as Claude Code's."""
    with tempfile.TemporaryDirectory(prefix='swe-final-', ignore_cleanup_errors=True) as d:
        final = Path(d) / 'repo'
        shutil.copytree(base, final, symlinks=True, ignore=shutil.ignore_patterns('.prepared'))
        for c in changes:
            p = final / c['path']
            if c.get('deleted'):
                p.unlink(missing_ok=True)
            elif c.get('after') is not None:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(c['after'])
        return make_patch(base, final)


def image_of(instance_id):
    return f"swebench/sweb.eval.x86_64.{instance_id.replace('__', '_1776_')}:latest"


def harness(workdir, preds, run_id, instance_id, dataset=DATASET):
    """One instance through the official harness; returns its report (or None). The harness's own output
    goes to harness.log in the workdir, so a run that stops before the instance can be read."""
    with open(Path(workdir) / 'harness.log', 'a') as out:
        out.write(f'--- {run_id} {instance_id}\n')
        out.flush()
        subprocess.run([sys.executable, '-m', 'swebench.harness.run_evaluation', '-d', dataset, '-p', str(preds),
                        '-id', run_id, '--max_workers', '1', '-i', instance_id], cwd=workdir, check=False,
                       stdout=out, stderr=subprocess.STDOUT)
    model = 'gold' if preds == 'gold' else json.loads(Path(preds).read_text().splitlines()[0])['model_name_or_path']
    rep = Path(workdir) / 'logs' / 'run_evaluation' / run_id / model / instance_id / 'report.json'
    return json.loads(rep.read_text()).get(instance_id) if rep.exists() else None


def evaluate(args):
    """Grade every agent's patches and the gold patch, one instance at a time (each evaluation image is
    ~4 GB: pulled for amd64, used for every patch of that instance, then removed). Writes, per results
    file, the same lines with 'accepted' (resolved by the harness), plus gold-validity.json. An instance
    whose gold patch does not resolve here is invalid: the page and summary leave it out for every agent."""
    workdir = Path(args.workdir); workdir.mkdir(parents=True, exist_ok=True)
    task_list = json.loads(Path(args.tasks).read_text())
    tasks = [t['id'] for t in task_list]
    dataset = task_list[0]['acceptance']['command'].split()[0]
    files = [spec.split('=', 1) for spec in args.results]
    runs = {label: [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()] for label, path in files}
    for label, rs in runs.items():
        for r in rs:
            if 'patch' not in r and 'changes' in r:
                r['patch'] = patch_from_changes(Path(args.repos) / r['task'], r['changes'])
    validity_path = workdir / 'gold-validity.json'
    validity = json.loads(validity_path.read_text()) if validity_path.exists() else {}
    verdicts = json.loads((workdir / 'verdicts.json').read_text()) if (workdir / 'verdicts.json').exists() else {}
    def todo_of(iid):
        return [(label, r) for label, rs in runs.items() for r in rs if r['task'] == iid and f"{label}|{r.get('rep', 1)}|{iid}" not in verdicts]

    def pull(iid):
        return subprocess.Popen(['docker', 'pull', '-q', '--platform', 'linux/amd64', image_of(iid)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def present(iid):
        return subprocess.run(['docker', 'image', 'inspect', image_of(iid)], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode == 0

    # The next instance's image downloads while this one is graded (a pull takes minutes; grading is unchanged).
    pending = [iid for iid in tasks if iid not in validity or todo_of(iid)]
    pulls = {}
    for n, iid in enumerate(pending):
        todo = todo_of(iid)
        (pulls.pop(iid, None) or pull(iid)).wait()
        # Without its image the harness stops before the instance and writes no report: pull it again, and
        # grade nothing for this instance if it is still missing (a harness error, retried by the next evaluate).
        for _ in range(2):
            if present(iid):
                break
            pull(iid).wait()
        if not present(iid):
            print(f'HARNESS ERROR {iid}: its evaluation image could not be pulled', flush=True)
            continue
        if n + 1 < len(pending):
            pulls[pending[n + 1]] = pull(pending[n + 1])
        if iid not in validity:
            g = harness(workdir, 'gold', 'gold', iid, dataset)
            if g is None:
                # No report for the gold patch is the harness failing (it stopped before the instance ran),
                # not an invalid instance: nothing is recorded, so the next evaluate grades it again.
                print(f'HARNESS ERROR gold {iid}: no report (see {workdir}/logs/run_evaluation/gold)', flush=True)
            else:
                validity[iid] = {'resolved': bool(g.get('resolved')), 'report': g}
                validity_path.write_text(json.dumps(validity, indent=1) + '\n')
        for label, r in todo:
            # The harness names a Docker container after the run id: letters, digits, _ . - only.
            model = re.sub(r'[^A-Za-z0-9_.-]+', '-', f"{label}-rep{r.get('rep', 1)}")
            if not (r.get('patch') or '').strip():
                verdicts[f"{label}|{r.get('rep', 1)}|{iid}"] = {'resolved': False, 'why': 'empty patch'}
                continue
            preds = workdir / f'{model}.{iid}.preds.jsonl'
            preds.write_text(json.dumps({'instance_id': iid, 'model_name_or_path': model, 'model_patch': r['patch']}) + '\n')
            rep = harness(workdir, preds, model, iid, dataset)
            log = workdir / 'logs' / 'run_evaluation' / model / model / iid / 'run_instance.log'
            if rep is None and log.exists() and APPLY_PATCH_FAIL in log.read_text(errors='replace'):
                # The harness's own verdict on the agent's patch (git apply and patch --fuzz=5 both
                # refused it): not resolved, as in the official SWE-bench report.
                verdicts[f"{label}|{r.get('rep', 1)}|{iid}"] = {'resolved': False, 'why': 'patch does not apply', 'applied': False}
                continue
            if rep is None:
                # No report is the harness failing, not the agent: nothing is recorded, so the next
                # evaluate retries it, and no graded file is written while any verdict is missing.
                print(f'HARNESS ERROR {label} {iid}: no report (see {workdir}/logs/run_evaluation/{model})', flush=True)
                continue
            verdicts[f"{label}|{r.get('rep', 1)}|{iid}"] = {'resolved': bool(rep.get('resolved')),
                                                         'why': 'resolved' if rep.get('resolved') else 'not resolved',
                                                         'applied': bool(rep.get('patch_successfully_applied'))}
        (workdir / 'verdicts.json').write_text(json.dumps(verdicts, indent=1) + '\n')
        if not args.keep_images:
            # Images of one project share layers: removing this one while the next is still downloading can
            # break that download, so the removal waits for it.
            nxt = pulls.get(pending[n + 1]) if n + 1 < len(pending) else None
            if nxt:
                nxt.wait()
            subprocess.run(['docker', 'rmi', '-f', image_of(iid)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(iid, 'gold', validity.get(iid, {}).get('resolved'), {k.split('|')[0]: v['resolved'] for k, v in verdicts.items() if k.endswith('|' + iid)}, flush=True)
    missing = [f"{label}|{r.get('rep', 1)}|{r['task']}" for label, rs in runs.items() for r in rs
               if f"{label}|{r.get('rep', 1)}|{r['task']}" not in verdicts]
    missing += [f'gold|{iid}' for iid in tasks if iid not in validity]
    if missing:
        sys.exit(f'{len(missing)} runs have no verdict (harness errors); run evaluate again: {missing}')
    for label, path in files:
        out = []
        for r in runs[label]:
            v = verdicts.get(f"{label}|{r.get('rep', 1)}|{r['task']}", {})
            out.append(dict(r, accepted=bool(v.get('resolved')), grade_detail=v.get('why', 'not graded'),
                            gold_valid=bool(validity.get(r['task'], {}).get('resolved')),
                            graded_by=f'swebench {__import__("swebench").__version__ if hasattr(__import__("swebench"), "__version__") else ""} ({dataset})'))
        Path(path).with_suffix('.graded.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in out))
        print(label, sum(x['accepted'] for x in out), 'resolved of', len(out))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('select'); s.add_argument('--out', default=ROOT / 'tasks' / 'swe-lite.json')
    s.add_argument('--seed', type=int, default=SEED); s.add_argument('--set-name', default='swe-lite')
    s.add_argument('--exclude', nargs='*', help='task files whose instances are left out (a fresh sample)')
    s.add_argument('--dataset', default=DATASET); s.add_argument('--n', type=int, default=N)
    s.add_argument('--difficulty', nargs='*', help="only instances with these difficulty labels (Verified)")
    p = sub.add_parser('prepare'); p.add_argument('--tasks', default=ROOT / 'tasks' / 'swe-lite.json'); p.add_argument('--repos', required=True)
    e = sub.add_parser('evaluate')
    e.add_argument('results', nargs='+', help='label=results.jsonl')
    e.add_argument('--tasks', default=ROOT / 'tasks' / 'swe-lite.json'); e.add_argument('--repos', required=True)
    e.add_argument('--workdir', default='swe-eval'); e.add_argument('--keep-images', action='store_true')
    args = ap.parse_args()
    {'select': select, 'prepare': prepare, 'evaluate': evaluate}[args.cmd](args)


if __name__ == '__main__':
    main()
