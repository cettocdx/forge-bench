"""Claude Code arm of the Claude-vs-RIFT benchmark.

Runs the same tasks as `bench::live::live_benchmark` (exported by `bench::tests::export_tasks`)
through headless Claude Code (`claude -p`), then judges the final tree with the same hidden
acceptance tests in the same network-less containers. One JSON line per run, nothing decided here.

Isolation: fresh temp project per run, no user/project settings, no MCP servers, no skills, no
session persistence, Claude Code's own sandbox on (writes confined to the project, no network).
"""
from pathlib import Path
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile, threading, time

SKIP_DIRS = {'.claude', '.git', 'node_modules', '__pycache__', 'hidden'}
SETTINGS = {'sandbox': {'enabled': True, 'autoAllowBashIfSandboxed': True}}


def write_tree(root, files):
    for path, content in files:
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def read_tree(root):
    tree = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root)
        if p.is_file() and not (set(rel.parts[:-1]) & SKIP_DIRS) and rel.parts[0] not in SKIP_DIRS:
            tree.append((rel.as_posix(), p.read_bytes()))
    return tree


def accept(task, tree):
    """Same as bench::accept: hidden tests over the final tree, network-less container."""
    with tempfile.TemporaryDirectory(prefix='ccbench-acc-') as d:
        root = Path(d)
        for path, data in tree:
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(data)
        write_tree(root, task['hidden'])
        acc = task['acceptance']
        out = subprocess.run(['docker', 'run', '--rm', '--network', 'none', '-v', f'{root}:/w', '-w', '/w',
                              acc['image'], 'sh', '-c', acc['command']], capture_output=True, text=True)
        return out.returncode == 0, (out.stdout + out.stderr)[-1500:]


def usage_of(result):
    """Totals over every model Claude Code used (main model plus any background model)."""
    keys = dict(uncached_input='inputTokens', cached_read='cacheReadInputTokens',
                cache_write='cacheCreationInputTokens', output_tokens='outputTokens', cost_usd='costUSD')
    per_model = result.get('modelUsage') or {}
    totals = {k: sum((m.get(v) or 0) for m in per_model.values()) for k, v in keys.items()}
    totals['input_tokens'] = totals['uncached_input'] + totals['cached_read'] + totals['cache_write']
    totals['models'] = sorted(per_model)
    totals['usage_complete'] = bool(per_model) and result.get('total_cost_usd') is not None
    if result.get('total_cost_usd') is not None:
        totals['cost_usd'] = result['total_cost_usd']
    return totals


def claude_version():
    out = subprocess.run(['claude', '--version'], capture_output=True, text=True)
    return out.stdout.strip() or None


def docker_version():
    out = subprocess.run(['docker', 'version', '--format', '{{.Server.Version}}'], capture_output=True, text=True)
    return out.stdout.strip() or None


def child_env():
    env = dict(os.environ)
    for k in ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT'):
        env.pop(k, None)
    return env


def run_one(task, rep, args):
    project = Path(tempfile.mkdtemp(prefix='ccbench-'))
    try:
        if task.get('swe'):
            # a SWE-bench task: the prepared repository, graded later by the SWE-bench harness
            shutil.rmtree(project)
            shutil.copytree(Path(args.repos) / task['id'], project, symlinks=True, ignore=shutil.ignore_patterns('.prepared'))
        else:
            write_tree(project, task['files'])
        cmd = ['claude', '-p', task['request'], '--model', args.model, '--effort', args.effort,
               '--output-format', 'json', '--permission-mode', 'bypassPermissions',
               '--setting-sources', 'project', '--strict-mcp-config', '--disable-slash-commands',
               '--no-session-persistence', '--settings', json.dumps(SETTINGS)]
        if not task['allow_exec']:
            cmd += ['--disallowedTools', 'Bash']
        started = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=project, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=child_env())
        if task.get('concurrent_edit'):
            path, content = task['concurrent_edit']
            threading.Timer(3, lambda: (project / path).write_text(content)).start()
        try:
            stdout, stderr = proc.communicate(timeout=args.timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            timed_out = True
        seconds = time.monotonic() - started
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = {}
        patch = None
        if task.get('swe'):
            from swe_tasks import make_patch
            patch = make_patch(Path(args.repos) / task['id'], project)
            accepted, detail = None, 'graded by the SWE-bench harness'
        else:
            accepted, detail = accept(task, read_tree(project))
        if accepted and task.get('concurrent_edit'):
            path, content = task['concurrent_edit']
            kept = (project / path).read_text() == content
            if not kept:
                accepted, detail = False, 'user edit kept: False'
        line = dict(task=task['id'], set=task['set'], held_out=task['held_out'], arm='CC', rep=rep,
                    state='timeout' if timed_out else result.get('subtype', 'no_result'),
                    is_error=result.get('is_error'), accepted=accepted, turns=result.get('num_turns'),
                    seconds=seconds, **usage_of(result))
        if patch is not None:
            line['patch'] = patch
        if accepted is False:
            line['detail'] = detail[-300:]
            if not result:
                line['stderr'] = stderr[-500:]
        return line
    finally:
        shutil.rmtree(project, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', required=True, help='task file in the export_tasks schema')
    ap.add_argument('--out', required=True)
    ap.add_argument('--set', default='all', help="only tasks of this set (e.g. standard, hard, polyglot-py)")
    ap.add_argument('--filter', default='', help='comma-separated substrings of task ids')
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--model', default='claude-opus-5-5')
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--timeout', type=int, default=1200)
    ap.add_argument('--budget-usd', type=float, default=30.0)
    ap.add_argument('--repos', help='prepared repositories for SWE-bench tasks (swe_tasks.py prepare)')
    args = ap.parse_args()
    raw = Path(args.tasks).read_bytes()
    tasks = json.loads(raw)
    tasks = [t for t in tasks if args.set in ('all', t['set'])
             and (not args.filter or any(f in t['id'] for f in args.filter.split(',')))]
    version = claude_version()
    # The setup of this run, next to its results (same idea as rift-bench's meta file).
    Path(args.out + '.meta.json').write_text(json.dumps({
        'tool': 'run_claude.py', 'agent': 'claude-code', 'agent_version': version,
        'os': platform.system().lower(), 'arch': platform.machine(), 'docker': docker_version(),
        'model': args.model, 'effort': args.effort, 'settings': SETTINGS,
        'flags': ['--permission-mode', 'bypassPermissions', '--setting-sources', 'project', '--strict-mcp-config',
                  '--disable-slash-commands', '--no-session-persistence'],
        'reps': args.reps, 'tasks': [{'path': str(args.tasks), 'sha256': hashlib.sha256(raw).hexdigest()}],
        'task_count': len(tasks), 'budget_usd': args.budget_usd, 'started_at_ms': int(time.time() * 1000),
    }, indent=2) + '\n')
    spent = 0.0
    with open(args.out, 'a') as out:
        for rep in range(1, args.reps + 1):
            for task in tasks:
                if spent > args.budget_usd:
                    print(json.dumps({'stopped': 'budget', 'spent_usd': spent}), file=out, flush=True)
                    return
                line = run_one(task, rep, args)
                spent += line.get('cost_usd') or 0
                line.update(agent='claude-code', agent_version=version, model=args.model, effort=args.effort)
                line['spent_usd'] = spent
                print(json.dumps(line), file=out, flush=True)
                print(f"{task['id']} rep{rep}: accepted={line['accepted']} ${line.get('cost_usd', 0):.4f} "
                      f"{line['seconds']:.0f}s", file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
