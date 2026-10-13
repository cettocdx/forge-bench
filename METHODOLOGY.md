# Methodology

## The question

With the **same model at the same reasoning effort**, on the **same tasks**, judged by the **same
hidden tests**: how often does each agent deliver a correct result, and how many tokens, dollars,
turns and seconds does it spend doing it?

## The two agents

| | Forge | Claude Code |
|---|---|---|
| Runner | `rift-bench` (headless build of Forge's Rust core) | `harness/run_claude.py`, which calls `claude -p` |
| Model | `anthropic/claude-opus-5.5` through OpenRouter | `claude-opus-5-5` through Anthropic |
| Reasoning effort | medium | medium (`--effort medium`) |
| Context | Forge's defaults: the structural context engine and prompt caching | Claude Code's defaults |
| Commands | In Forge's Docker sandbox (no network except package registries when allowed) | Claude Code's own sandbox (`sandbox.enabled`), writes confined to the project |
| Configuration | None: a fresh data directory per run | None: `--setting-sources project` in an empty project, `--strict-mcp-config`, `--disable-slash-commands`, `--no-session-persistence` |
| Permissions | Forge's own (no prompts in a benchmark run) | `--permission-mode bypassPermissions` inside the sandbox; `Bash` removed for tasks that forbid running commands |

Each run starts from an empty temporary project holding only the task's starting files, with no
history, memory, user settings, MCP servers, skills or plugins. Both agents receive the task's
request text unchanged.

## Acceptance

A run counts as **accepted** only if the task's hidden tests pass on the agent's final tree. The
hidden tests are never in the agent's project. They run after the agent has stopped, in a
container with no network (`node:24-alpine` or `python:3.13-alpine`), with the same command for
both agents. For the concurrent-edit task, the user's edit must also survive.

Every task was checked before any run: its hidden tests fail on the starting project and pass on
the reference solution (`bench_tasks_are_sound`, `hard_tasks_are_sound`, `polyglot_tasks.py --check`).

## SWE-bench: the large tasks

Three samples of [SWE-bench](https://www.swebench.com): real GitHub issues in real repositories. SWE-bench Lite is
the benchmark Aider reported its SWE-bench results on; SWE-bench Verified's issues carry an estimate, by
SWE-bench's annotators, of how long an engineer needs to fix them.

This uses Aider's SWE-bench in the sense of its dataset and its grading: SWE-bench Lite, judged by the official
SWE-bench harness, one attempt per instance. The agents compared are Forge and Claude Code; Aider itself is not
run. Aider's published score covers all 300 Lite instances; here 40 of them are used (two seeded samples of 20),
plus 10 hard Verified instances, so the resolution rates have wide intervals.

| Sample | Task file | How it was drawn | Role |
|---|---|---|---|
| Fresh | `tasks/swe-lite-test.json` | 20 of Lite's 300, seed 20261014, none from the development sample | Measurement |
| Hard | `tasks/swe-verified-hard.json` | 10 of the 45 Verified instances annotated "1-4 hours" or ">4 hours", seed 20261015, none from the Lite samples | Measurement |
| Development | `tasks/swe-lite.json` | 20 of Lite's 300, seed 20261013 | Found Forge's problems and checked the fixes |

- **Selection.** `harness/swe_tasks.py select` draws each sample with its fixed seed before any agent runs on it.
  Nothing was picked or dropped by hand.
- **The task.** Each agent gets the repository at the issue's base commit (without `.git`) and the same request: the
  issue text and "fix the issue by changing the library's source code; do not edit or add tests". One run per
  instance per agent.
- **The patch.** For both agents the patch is made the same way: the final tree is compared with the prepared
  repository by `git diff`, with run artefacts (`__pycache__`, `.pyc`, caches, `.egg-info`) left out and symbolic
  links kept as links.
- **Grading.** The official SWE-bench harness (`swebench` 5.0.2) with the published evaluation images: the
  instance's own environment, the agent's patch, then the hidden test patch; *resolved* means every FAIL_TO_PASS and
  PASS_TO_PASS test passes. The images are amd64 and run under emulation on Apple silicon; that changes speed, not
  results.
- **Validity.** Every instance's gold (reference) patch is graded in the same run. An instance whose gold patch does
  not resolve here is left out for every agent, whatever the agents did. Each graded run's folder has `grading/`:
  `gold-validity.json`, the verdicts, and the harness's own report for every instance.
- **Harness errors are not failures.** If the harness produces no report for a patch (as when a run id is not a
  valid Docker name), no verdict is recorded and no graded file is written until it is graded again.
- **Large and small.** The headline for large tasks pools the fresh and the hard samples, the two nobody tuned Forge
  on. The development sample is reported on its own.

### What the SWE-bench runs found in Forge, and what we looked at

Forge's first runs on large repositories cost several times what Claude Code spent. Each problem was found by reading
a run's record, fixed in Forge's core with a test, and every official Forge run was made again on the fixed build.
None of the fixes names a repository or an instance:

| Build | Problem found | Fix |
|---|---|---|
| 9d64c6e | The context block listed every left-out symbol (~120k tokens on Django); a Python project with a `package.json` was taken for Node; framework templates were taken for a web page | Bounded list; Python wins over a stray `package.json`; only a top-level `index.html` is a page |
| 4396ec6 | A test suite that cannot load in the sandbox sent the model to "repair" failures that were there before its change | Reported as unverified instead |
| 81ee14b | Failures that existed before the change, in tests unrelated to it, still started repairs; common names filled the context block | Repairs only for failures the change can have caused; common names weigh less |
| 0f836d2 | The note on the first edit carried 90 KB of import errors and a second selection; compaction at 64k tokens rewrote the whole prompt cache; whole-file reads of 2,000-line files; lists of 500 test names; a repair round for test files that need a module the sandbox lacks | A one-line note; compaction near the window when caching; long files read as an outline first; names capped; such failures reported, not repaired |
| 552d23f | After the completion check the model rewrote its whole summary | It can keep the summary as written |
| 61463e9 | On large projects the context block and the first-edit note held thousands of same-named occurrences and unrelated code | Smaller block (3k tokens) and no selection there on large projects |
| fa7ceb7 | The fixed prompt prefix was rewritten whenever two tasks were more than five minutes apart | It is cached for an hour (the conversation keeps five minutes) |

What we looked at, so you can discount it:

- **Development sample.** Forge's runs on `django__django-11019`, `-11964`, `-12497`, `-13220`,
  `matplotlib__matplotlib-22711`, `pytest-dev__pytest-11143`, `sympy__sympy-13177`, `-15308` and `-23191` were read
  while fixing Forge. The whole sample is reported as development, apart from the headline.
- **Fresh sample.** One instance, `django__django-12284`, was looked at: Forge's run on it cost five times Claude
  Code's and its trace led to the 0f836d2 fixes. The fresh sample is also reported without it ("never looked at").
- **Hard sample.** Nothing in it was looked at before the published build ran.
- Every stopped, aborted and development run is in `runs/` with its reason, and none of them is counted.

- **One discarded run.** The first Claude Code run on `django__django-11019` was made with a bug in our
  patch maker (symbolic links were followed in one tree and kept in the other, so unrelated files
  showed as changed). The bug was fixed and Claude Code's SWE runs were restarted from scratch; the
  discarded record is kept in the repository and marked as such.

## Ablations: the same change on both sides

Every ablation is run on both agents with one change from the official setup, on the polyglot set,
one repeat: reasoning effort `low` instead of `medium`, and Claude Sonnet 5.5 instead of Opus 5.5.
The leaderboards compare every agent × model × effort pair this produces.

## Measures

| Measure | Definition |
|---|---|
| Success rate | Accepted runs ÷ all runs, with a 95% Wilson score interval |
| Cost per run | The provider's cost for every model call of the run, failed attempts and repairs included |
| Cost per accepted task | Total cost of all runs ÷ accepted runs |
| Input tokens | All prompt tokens: uncached + cache read + cache write. OpenRouter reports Forge's prompt tokens this way; Claude Code's three Anthropic fields are added up to match |
| Output tokens | Completion tokens, reasoning included |
| Turns | Model calls of the main agent |
| Time | Wall-clock seconds from start to the agent's final state (median and 90th percentile) |

### What the cost numbers are

- **Forge:** the cost OpenRouter reports for each call, which is what OpenRouter charged.
  OpenRouter's fee for buying credits is not included.
- **Claude Code:** `total_cost_usd` from Claude Code's own JSON output, Anthropic's list price for
  the tokens used. On a Claude subscription this is an estimate, not a bill.

Both use the same model at the same list prices, so the two figures are comparable. They are not
both invoices.

## Procedure

- **Repeats:** official runs have two repeats of every small task and one run of every SWE-bench instance for
  each agent.
- **Prompt cache:** Forge marks its fixed prefix (tools and system prompt) for a one-hour cache and the conversation
  for five minutes; Claude Code uses its own caching. Both are each product's default.
- **Concurrency:** the two agents' runs were executed at the same time on one machine. Wall-clock
  times therefore include shared machine load. Tokens and cost are not affected by it.
- **Cache warmth:** a provider's prompt cache can stay warm between consecutive runs of the same
  agent. This happens to both agents, as it would in daily use.
- **Machine:** one Mac (macOS, Apple silicon), Docker 29.8.

## Kinds of runs, and nothing deleted

`runs/` keeps every run we made, including the ones that do not make the headline:

| Kind | What it is |
|---|---|
| `official` | The comparison: the published `rift-bench` build against Claude Code (two repeats on the small tasks, one run per SWE-bench instance). |
| `exploratory` | Earlier builds, stopped runs and development runs (the ones that found and checked Forge's fixes). |
| `ablation` | One change at a time, on both agents: reasoning effort low; Claude Sonnet 5.5. |
| `aborted` | Runs stopped by a problem (in Forge or in our harness) and made again from scratch. Not counted. |

Each run folder has `run.json` (label, kind, date), `meta.json` (versions, model, effort, flags,
SHA-256 of the task file) and `results.jsonl` (one line per task run, exactly as the runner wrote
it). Forge's later runs also have `traces/`: the whole conversation of each run (`rift-bench --traces`), so every
token can be traced to what the model read and wrote. For runs made before the runners wrote meta files, `meta.json` is marked
`"reconstructed": true` and was written from the runner's source.

## Errors, results and the agents' own verdicts

- **An infrastructure error is never counted.** `harness/check_runs.py` checks every official and ablation run of
  both agents: no runner error, complete token usage, an official SWE-bench verdict and a valid gold patch for
  every instance with the harness's report kept, and the same tasks run the same number of times by both agents.
  Its output is `results/integrity.txt`; it exits with an error if anything fails.
- **A task an agent does not solve is a result, not an error.** It is counted against that agent.
- **An agent's end state is its own claim.** Forge ends a run SUCCEEDED, UNVERIFIED (its checks could not run or
  prove the change, as with hidden tests or a suite that does not load in its sandbox) or FAILED (its own checks
  still failed); Claude Code reports success. Neither decides acceptance: the hidden tests and the SWE-bench
  harness do. Three fresh-sample runs that Forge ended FAILED were resolved by the harness.
- Runs stopped by us, and one grading pass that hit a harness error (a run id that was not a valid Docker name),
  were made again; the stopped runs are in `runs/` as `aborted` or `exploratory` and never counted.

## Integrity

`MANIFEST.sha256` lists the SHA-256 of every file under `runs/`, `tasks/` and `results/`. Check it
with `shasum -a 256 -c MANIFEST.sha256`. `results/summary.json`, which the benchmark page displays,
is computed from `runs/` by `harness/summarize.py`; run it again and compare.

## Limits

- **One machine, one model.** Another machine, model or provider route may give other numbers.
- **Single-repository tasks.** The largest are real issues that annotators estimate take an engineer one to four
  hours; agents fix them in minutes. Long, multi-hour sessions and work across repositories are not measured.
- **One run per SWE-bench instance.** Thirty large tasks per agent give wide intervals around the resolution rates;
  they are printed next to every rate.
- **Success near the ceiling.** Both agents pass almost every task. These sets can show a failure
  rate of a few percent, but not small quality differences between strong agents.
- **Two repeats.** The intervals around the success rates are wide. They are shown next to every
  rate.
- **Two runtimes.** Forge runs Node.js and Python tasks, so the task sets are limited to those
  languages.
- **Different routes to the same model.** Forge reaches Opus 5.5 through OpenRouter and Claude Code
  reaches it through Anthropic. Their caches and latencies differ.
- **Not a measure of everything.** User experience, interface quality, long-running sessions and
  tasks outside a repository are not measured.
