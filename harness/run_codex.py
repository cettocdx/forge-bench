"""Codex arm: the same tasks as Forge and Claude Code, through headless Codex (`codex exec`).

Each run gets a fresh project and a fresh, empty CODEX_HOME holding only the model provider, so no
user config, AGENTS.md, skills, plugins, MCP servers, rules or session history take part. The model
is called through OpenRouter (env OPENROUTER_API_KEY), the account and price list Forge's runs use.
Codex's own sandbox is on (workspace-write: writes confined to the project, no network); host
integrations (apps, plugins, browser and computer use) are off, as Claude Code runs without MCP or
plugins. Codex reads files only through its shell, so a task that disables commands for the other
agents keeps Codex's shell (marked shell_kept). The final tree is judged with the same hidden acceptance tests in the same network-less
containers (SWE-bench tasks: the patch, graded later by swe_tasks.py). One JSON line per run.

Codex reports tokens, not cost: a run's cost is its tokens at the model's OpenRouter list prices
(uncached input, cache reads, cache writes, output and reasoning output), read once at the start
and kept in the meta file.
"""
from pathlib import Path
import argparse, hashlib, json, os, platform, shutil, subprocess, sys, tempfile, threading, time, urllib.request

from run_claude import accept, docker_version, read_tree, write_tree

OPENROUTER = 'https://openrouter.ai/api/v1'
HOST_FEATURES = ['apps', 'plugins', 'browser_use', 'browser_use_external', 'computer_use', 'in_app_browser']
FLAGS = ['--json', '--skip-git-repo-check', '--ephemeral', '--ignore-rules', '-s', 'workspace-write']


def prices_of(model):
    """The model's OpenRouter list prices in USD per token (prompt, completion, cache read and write)."""
    with urllib.request.urlopen(f'{OPENROUTER}/models', timeout=30) as r:
        for m in json.load(r)['data']:
            if m['id'] == model:
                p = m['pricing']
                prompt = float(p['prompt'])
                return {'prompt': prompt, 'completion': float(p['completion']),
                        'input_cache_read': float(p.get('input_cache_read') or prompt),
                        'input_cache_write': float(p.get('input_cache_write') or prompt),
                        'overrides': p.get('overrides') or []}
    sys.exit(f'{model} is not in the OpenRouter model list')


def codex_home(model, effort):
    home = Path(tempfile.mkdtemp(prefix='cxhome-'))
    (home / 'config.toml').write_text(
        f'model = "{model}"\nmodel_provider = "openrouter"\nmodel_reasoning_effort = "{effort}"\n\n'
        '[model_providers.openrouter]\nname = "OpenRouter"\nbase_url = "https://openrouter.ai/api/v1"\n'
        'env_key = "OPENROUTER_API_KEY"\nwire_api = "responses"\n')
    return home


def usage_of(events, prices):
    """Totals over every turn Codex reports, priced at the list prices."""
    t = dict(input_tokens=0, cached_read=0, cache_write=0, output_tokens=0, reasoning_tokens=0)
    turns = 0
    for e in events:
        if e.get('type') == 'turn.completed' and isinstance(e.get('usage'), dict):
            u = e['usage']
            turns += 1
            t['input_tokens'] += u.get('input_tokens') or 0
            t['cached_read'] += u.get('cached_input_tokens') or 0
            t['cache_write'] += u.get('cache_write_input_tokens') or 0
            t['output_tokens'] += u.get('output_tokens') or 0
            t['reasoning_tokens'] += u.get('reasoning_output_tokens') or 0
    t['uncached_input'] = max(t['input_tokens'] - t['cached_read'] - t['cache_write'], 0)
    t['cost_usd'] = (t['uncached_input'] * prices['prompt'] + t['cached_read'] * prices['input_cache_read']
                     + t['cache_write'] * prices['input_cache_write']
                     + (t['output_tokens'] + t['reasoning_tokens']) * prices['completion'])
    # Codex reports usage per turn, not per request: a request over the long-context threshold would be
    # priced higher than this, so such a run's cost is a lower bound.
    t['usage_complete'] = turns > 0
    return t


def tool_calls(events):
    kinds = ('command_execution', 'file_change', 'web_search', 'mcp_tool_call')
    return sum(1 for e in events if e.get('type') == 'item.completed' and (e.get('item') or {}).get('type') in kinds)


def codex_version():
    out = subprocess.run(['codex', '--version'], capture_output=True, text=True)
    return out.stdout.strip() or None


def run_one(task, rep, args, prices):
    project = Path(tempfile.mkdtemp(prefix='cxbench-'))
    home = codex_home(args.model, args.effort)
    try:
        if task.get('swe'):
            shutil.rmtree(project)
            shutil.copytree(Path(args.repos) / task['id'], project, symlinks=True, ignore=shutil.ignore_patterns('.prepared'))
        else:
            write_tree(project, task['files'])
        cmd = ['codex', 'exec', *FLAGS, '-C', str(project)]
        for f in HOST_FEATURES:
            cmd += ['--disable', f]
        # Codex reads files only through its shell (without it, it can edit but not read), so a task
        # that disables commands for Forge and Claude Code keeps Codex's shell: on those tasks Codex
        # has one capability more than the other agents, and its record says so.
        cmd.append(task['request'])
        env = dict(os.environ, CODEX_HOME=str(home))
        started = time.monotonic()
        proc = subprocess.Popen(cmd, cwd=project, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
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
        events = []
        for l in stdout.splitlines():
            try:
                events.append(json.loads(l))
            except json.JSONDecodeError:
                pass
        failed = [e for e in events if e.get('type') in ('error', 'turn.failed')]
        finished = any(e.get('type') == 'turn.completed' for e in events)
        state = 'timeout' if timed_out else ('success' if finished and not failed else 'error')
        patch = None
        if task.get('swe'):
            from swe_tasks import make_patch
            patch = make_patch(Path(args.repos) / task['id'], project)
            accepted, detail = None, 'graded by the SWE-bench harness'
        else:
            accepted, detail = accept(task, read_tree(project))
        if accepted and task.get('concurrent_edit'):
            path, content = task['concurrent_edit']
            if (project / path).read_text() != content:
                accepted, detail = False, 'user edit kept: False'
        line = dict(task=task['id'], set=task['set'], held_out=task['held_out'], arm='CX', rep=rep, state=state,
                    is_error=bool(failed) or (not finished and not timed_out), accepted=accepted,
                    turns=tool_calls(events), seconds=seconds, **usage_of(events, prices))
        if not task['allow_exec']:
            line['shell_kept'] = True
        if failed:
            line['error'] = json.dumps(failed[-1])[-500:]
        if patch is not None:
            line['patch'] = patch
        if accepted is False:
            line['detail'] = detail[-300:]
            if not events:
                line['stderr'] = stderr[-500:]
        return line
    finally:
        shutil.rmtree(project, ignore_errors=True)
        shutil.rmtree(home, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tasks', required=True, help='task file in the export_tasks schema')
    ap.add_argument('--out', required=True)
    ap.add_argument('--set', default='all', help='only tasks of this set (e.g. standard, hard, polyglot-py)')
    ap.add_argument('--filter', default='', help='comma-separated substrings of task ids')
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--model', default='openai/gpt-6-astra', help='OpenRouter model id')
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--timeout', type=int, default=3600)
    ap.add_argument('--budget-usd', type=float, default=30.0)
    ap.add_argument('--repos', help='prepared repositories for SWE-bench tasks (swe_tasks.py prepare)')
    args = ap.parse_args()
    if not os.environ.get('OPENROUTER_API_KEY'):
        sys.exit('set OPENROUTER_API_KEY (Codex calls the model through OpenRouter)')
    raw = Path(args.tasks).read_bytes()
    tasks = [t for t in json.loads(raw) if args.set in ('all', t['set'])
             and (not args.filter or any(f in t['id'] for f in args.filter.split(',')))]
    version, prices = codex_version(), prices_of(args.model)
    Path(args.out + '.meta.json').write_text(json.dumps({
        'tool': 'run_codex.py', 'agent': 'codex', 'agent_version': version,
        'os': platform.system().lower(), 'arch': platform.machine(), 'docker': docker_version(),
        'model': args.model, 'effort': args.effort, 'provider': 'openrouter', 'prices_usd_per_token': prices,
        'flags': FLAGS + [f'--disable {f}' for f in HOST_FEATURES], 'codex_home': 'fresh and empty per run',
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
                line = run_one(task, rep, args, prices)
                spent += line.get('cost_usd') or 0
                line.update(agent='codex', agent_version=version, model=args.model, effort=args.effort)
                line['spent_usd'] = spent
                print(json.dumps(line), file=out, flush=True)
                print(f"{task['id']} rep{rep}: accepted={line['accepted']} ${line.get('cost_usd', 0):.4f} "
                      f"{line['seconds']:.0f}s", file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
