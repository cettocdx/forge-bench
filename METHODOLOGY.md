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
| Web on SWE-bench tasks | Off (from 30eb649) | `WebSearch` and `WebFetch` disallowed (runs from now on; see SWE-bench below) |
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

This is Aider's SWE-bench in its dataset and its grading: all 300 instances of SWE-bench Lite, judged by the
official SWE-bench harness, one attempt per instance. The agents compared are Forge and Claude Code; Aider itself
is not run.

| Sample | Task file | How it was drawn | Role |
|---|---|---|---|
| Fresh | `tasks/swe-lite-test.json` | 20 of Lite's 300, seed 20261014, none from the development sample | Measurement |
| The rest of Lite | `tasks/swe-lite-rest.json` | The 260 Lite instances in neither sample (seed 20261016 only orders them) | Measurement |
| Hard | `tasks/swe-verified-hard.json` | 10 of the 45 Verified instances annotated "1-4 hours" or ">4 hours", seed 20261015, none from the Lite samples | Measurement |
| Development | `tasks/swe-lite.json` | 20 of Lite's 300, seed 20261013 | Found Forge's problems and checked the fixes |

- **Selection.** `harness/swe_tasks.py select` draws each sample with its fixed seed before any agent runs on it.
  Nothing was picked or dropped by hand.
- **The task.** Each agent gets the repository at the issue's base commit (without `.git`) and the same request: the
  issue text and "fix the issue by changing the library's source code; do not edit or add tests". One run per
  instance per agent.
- **No web.** An instance is solved from its repository alone: on the web its fix is a search away. Forge's earlier
  runs had the web and sometimes used it to find the fix: in the 585ff1b run `sympy__sympy-16988` read the upstream
  pull request's diff, `pylint-dev__pylint-7114` a later release's code and tests and `sympy__sympy-16281` the fixed
  source; in the b8d60e9 run `sympy__sympy-11897` and `sympy__sympy-16988` read the pull request's diff and
  `sympy__sympy-12419` the fixed source. Every Forge SWE-bench run that used a web tool counts as unsolved wherever
  it is shown, whatever it read. From 30eb649 on,
  rift-bench turns the web off for SWE-bench tasks (the agent and its helpers are offered no web tool, and a web call
  reaches nothing; each record carries `"web": false`), and `run_claude.py` disallows `WebSearch` and `WebFetch` for
  Claude Code on them. Claude Code's SWE-bench runs here were made before that and had both tools; in none of them
  does the usage show a second model, which reading a page with `WebFetch` adds. Whether it searched is not recorded.
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
  valid Docker name), no verdict is recorded and no graded file is written until it is graded again. The same now
  holds for the gold patch. During 585ff1b's full run the harness stopped seven times before a gold patch's instance ran
  (its output was discarded then, so the cause is not known), and our grader recorded those gold patches as
  invalid: two instances were left out of the graded results for both agents, and the other five, graded valid in
  the other workdir, would have shown as invalid in the published grading. A gold verdict now comes only from the
  harness's report, the grader checks each image is present (and removes one only after the next has finished
  downloading, since images of a project share layers), the harness's output is kept in each workdir's
  `harness.log`, and `check_runs.py` fails any instance left out without a report. All seven were graded again;
  every one of their gold patches resolves. Two gradings sometimes ran in one workdir at once and one rewrote the
  other's verdict cache: 31 counted runs lost their entry there, and `grading/verdicts.json` gives it back from the
  harness's own report or log (marked `rebuilt_from`); every counted run's result agrees with its report.
- **A patch the harness cannot apply is not resolved.** When `git apply` and `patch --fuzz=5` both refuse an agent's
  patch, the harness writes no report but logs `Patch Apply Failed`; that run counts as not resolved, as in the
  official SWE-bench report, and the log is kept in `grading/reports/` in place of the report. The rule is the same
  for both agents.
- **One instance in two sets.** `sympy__sympy-17630` is a SWE-bench Lite instance and one of the 10 hard Verified
  ones, so each agent runs it once per set. Forge's full runs keep one run per instance id and run it only as a hard
  instance; it is then run once more as a Lite instance with the same build and settings
  (`runs/2026-10-17_swe-lite-rest-overlap_forge-30eb649_r1`). Claude Code's Lite run of it was first graded against the
  Verified spec (its test spec there is identical) and was graded again against Lite. In the pooled large-task
  numbers the instance counts once per set, for both agents alike.
- **One finished run per instance.** A run counts if it ended on its own, whatever it cost; only runs that never
  reached the model, were cut off by the provider, our credit or the machine's sleep, or were stopped by us are run
  again. During 585ff1b's full run our orchestrator also set aside eight *finished* Forge runs because their cost could not
  be fully measured (a web search's helper model whose charge Forge does not record, or a provider receipt without a
  price) and ran those instances again; `sympy__sympy-16988` searched the web every time and was run five times. That
  gave Forge a second chance on those instances, so the rule was applied after the fact: each instance's first
  finished attempt is the counted run, graded in its own workdir (`full/first/`), and the later attempts are kept as
  `runs/2026-10-14_swe-all_forge_reruns` (not counted). The eight counted runs' cost is a lower bound
  (`usage_complete: false`); their traces were overwritten by the re-runs, whose traces are in the re-runs folder.
  The first attempts resolved all 8. On the six instances whose re-run had been graded, the first attempts resolved
  6 and the re-runs 5 (`astropy__astropy-14369` only on its first attempt), so the rule counts one more instance for
  Forge than the re-runs did. Claude Code had no finished run set aside: its three set-aside runs ended in an API
  error during the network outage, as Forge's provider cut-offs did.
- **A gold patch that failed on an outside service is graded again, with both agents.** In 585ff1b's full run the gold
  patches of `psf__requests-1963` and `psf__requests-2317` failed tests that call httpbin.org, and that of
  `sympy__sympy-13146` failed one test; the agents' patches were graded in the same minutes, under the same
  conditions. The three instances were graded again, the gold patch and both agents' patches together
  (`full/regrade3/`), and that grading counts for all three: every gold patch resolves, Forge resolved 2 and Claude
  Code 3. No instance is left out.
- **A run the machine's sleep cut off is run again.** Forge's deadline is an hour of wall-clock time, while the
  run's own clock (and Claude Code's timeout) stops when the Mac sleeps. Two Forge runs reached that deadline after
  only 678 s and 2,413 s of run time: the Mac slept during them (its power log shows repeated sleep on 13 October),
  so they did not end on their own. `django__django-11910`'s next finished attempt counts;
  `astropy__astropy-13398` had no other and was run again with the same build, kept awake
  (`runs/2026-10-13_swe-all_forge_r1`, its record and trace; the cut run is with the set-aside records).
  `check_runs.py` now fails any counted run that reaches the deadline in less than an hour of run time.
- **30eb649's first run was lost, and run again in full.** A first full run of 30eb649 (16 October) was graded but
  not yet published when a restart of the Mac cleared the temporary folder holding its records. It was run again from
  scratch on 17 October with the same binary (the release's, sha256 `2a49612a…`), the same task files and the same
  settings, recovered from the session that started the first one. Only the run made again counts; nothing of the
  lost one is used. During the second run our OpenRouter credit ran out once: 57 runs were cut off by the provider's
  refusal (402) partway (within their first 106 s and 12 model calls). They are kept as `runs/2026-10-17_swe-all_forge-30eb649_infra-errors`, and
  each instance's next finished run counts. No finished run was set aside, every gold patch resolved, and one grader
  ran at a time. While the credit was out the orchestrator, seeing no runner busy, ended the run with those 57
  instances never started; its end condition was corrected and it was started again (no record changed).
- **Large and small.** The headline for large tasks pools every instance outside the development sample: the fresh
  sample, the rest of Lite and the hard sample (what of them was looked at is listed above, and the fresh and hard
  samples are also given without it). All 300 Lite instances are also reported together, as Aider reports them
  (development sample included), and the development sample on its own.

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
| 8899c7f | 43 of 63 searches named a file as their scope and all came back "no matches"; the model tried `git`, which the sandbox lacks | A file is a scope; the tool says there is no git |
| 585ff1b | 5 of 50 patches carried installed packages (`.deps/`) or `*.egg-info` build metadata; a check that ran no test could pass | Package metadata is never source, files the first test run creates are the starting state, packages go to `.venv` (outside the changes); no test run is not a pass |

After 585ff1b was published, its full run and runs with a second model (GPT-6 Astra, the model of the Codex
comparison) found the problems below. They were fixed the same way, and every official Forge run was made again: on
30eb649 for the comparison with Claude Code, and on 4b21037, which adds the last fix, for the one with Codex:

| Build | Problem found | Fix |
|---|---|---|
| 33d204b | Eight 585ff1b patches, all on pytest (`11143`, `11148`, `7373`, `7432`, `7490`, `8906`, `9359` and the hard `5787`), carried `src/_pytest/_version.py`, which the model's own `pip install -e .` generated and the evaluation image already has, so the harness could not apply them | Files a command or a check generates that the project's `.gitignore` ignores, and their later rewrites, are the starting state, not changes. The eight patches without that file were graded as a diagnostic (`runs/2026-10-15_swe-pytest_forge_diagnostic-no-version`, not counted) |
| e373e69 | Under heavy load (load average 70-115) sympy runs failed at the start with SQLite "database is locked": the first code index of a large project held the write lock for more than 20 s | The index commits in short parts. Those records cost nothing and were run again |
| 756f559 | 28% of Forge's SWE-bench cost went to setting up a project's own test runner and its whole dependency set, which rarely worked | The first message says the app runs the verification and asks for a quick, focused check instead |
| 2239a44 | With no package allowed, the model guessed where one quick check would have told (`sympy__sympy-15308`, development sample) | A quick check may install a package or two |
| b8d60e9 | The first quick check almost always failed on what the sandbox lacks (the project's packages, the modules Python 3.13 dropped, scratch files left in `/tmp`): two or three more calls a run | The first message names the packages the project declares and the one-command setup |
| 8b4dfc8 | With GPT-6 Astra, half the hard runs were compacted at about 30k tokens: OpenAI models cache prompts without cache markers, and Forge took them for uncached | A model that caches by itself compacts as a cached run |
| 12826bc | GPT-6 Astra sent about four to-do updates a run, each in a message of its own, a fifth of its cost (Claude never did, in 201 runs) | The to-do list is offered for long work only: a build, or a project that starts empty |
| ee6b2d3 | For a project with no tests to run, the first message said the app verifies the change (the polyglot exercises) | The plain line Forge had before 756f559 |
| 30eb649 | In the b8d60e9 run the model found upstream fixes on the web | No web on SWE-bench tasks (see SWE-bench above) |
| 4b21037 | In the comparison with Codex on GPT-6 Astra, links to Python's docs (`errors.html`) and "Score a bowling game" made Python exercises browser games: Forge offered the browser build and playtest tools and waited on browser evidence; Astra used them (py_bowling: 1,035 s, $1.27), Claude never did | Links are not read as the request's words, and words decide a browser UI only for a new build, a Node.js project or the games workbench; an existing Python project's own entry page still does. Forge's runs in that comparison were made again from the start on 4b21037 |

Two changes in between were replaced: beada79 asked for to-do updates to be sent with a step's call (GPT-6 Astra
ignored it), and 9380b6d asked for a thorough own check when there are no tests (it cost 25% more on polyglot).

One change was tried and taken back: running older projects on the Python they declare, with the project installed
in `.venv`. On six development instances it did not lower the cost and Python 3.10 and older print test names the
per-test parser cannot tell apart; the runs are in `runs/` as development runs.

What we looked at, so you can discount it:

- **Development sample.** Forge's runs on `django__django-11019`, `-11964`, `-12497`, `-13220`,
  `matplotlib__matplotlib-22711`, `pytest-dev__pytest-11143`, `sympy__sympy-13177`, `-15308` and `-23191` were read
  while fixing Forge, and every build from e373e69 to 30eb649 was checked on the whole sample. It is reported as
  development, apart from the headline.
- **Fresh sample.** `django__django-12284` was looked at before 585ff1b: Forge's run on it cost five times Claude
  Code's and its trace led to the 0f836d2 fixes. While 30eb649 was made, the first six instances (`django__django-12284`,
  `-14915`, `-14997`, `-15738`, `matplotlib__matplotlib-24265`, `pallets__flask-5063`) were run with GPT-6 Astra and
  those runs were read (they led to 8b4dfc8 and 12826bc, which leave Claude's runs as they were), and so was 585ff1b's
  patch for `matplotlib__matplotlib-24265` (the `_version.py` of 33d204b). The fresh sample is also reported without
  these six ("never looked at", 14 instances).
- **Hard sample.** Nothing in it was looked at before 585ff1b ran. While 30eb649 was made, its first six instances
  (`astropy__astropy-13398`, `-13579`, `-14369`, `django__django-13449`, `-13837`, `pylint-dev__pylint-4551`) were run
  with GPT-6 Astra and those runs were read. The hard sample is also reported without them ("never looked at", 4).
- **The other 260.** In the b8d60e9 run, the runs that used the web (`sympy__sympy-11870`, `-11897`, `-12419`,
  `-16988`) were read; they led to 30eb649's rule of no web on SWE-bench.
- **Polyglot.** The wordings for a project with no tests were compared on the polyglot exercises; 30eb649 keeps the
  plain line Forge had before.
- Every stopped, aborted and development run is in `runs/` with its reason, and none of them is counted.

- **One discarded run.** The first Claude Code run on `django__django-11019` was made with a bug in our
  patch maker (symbolic links were followed in one tree and kept in the other, so unrelated files
  showed as changed). The bug was fixed and Claude Code's SWE runs were restarted from scratch; the
  discarded record is kept in the repository and marked as such.

## A second comparison: Forge and Codex on GPT-6 Astra

The same question with OpenAI's model and OpenAI's agent: does the agent around GPT-6 Astra change what it solves and
what it costs? Both agents call `openai/gpt-6-astra` through OpenRouter (the same account and price list) at medium
reasoning effort.

| | Forge | Codex |
|---|---|---|
| Runner | `rift-bench` 4b21037 (30eb649 and the fix below) | `harness/run_codex.py`, which calls `codex exec` (Codex CLI 0.159.2) |
| Configuration | None: a fresh data directory per run | A fresh, empty `CODEX_HOME` per run holding only the model provider: no user config, `AGENTS.md`, skills, plugins, MCP servers, rules or history |
| Commands | Forge's Docker sandbox | Codex's own sandbox (`workspace-write`: writes confined to the project, no network) |
| Web on SWE-bench tasks | Off | `web_search = "disabled"` |
| Deadline | 1,200 s on a small task, an hour on an SWE-bench instance | The same |
| Cost | What OpenRouter charged for each call | Codex reports tokens, not cost: its tokens at the model's OpenRouter list prices (a run that timed out reports no usage for its last turn, so its cost is a lower bound) |

The tasks were fixed before any run: the Forge set and the polyglot exercises, two repeats (124 runs per agent), and
50 SWE-bench instances, one run each: the fresh sample (20), the hard sample (10) and `tasks/swe-lite-rest-20.json`,
20 instances of the rest of Lite drawn with seed 20261017 before any run on them. The first six instances of the fresh
and hard samples were run with GPT-6 Astra while 30eb649 was made, so those two samples are also given without them.
The SWE-bench patches of both agents and the gold patch were graded together by the official harness, five instances
and one dataset per group, one grader at a time. The same rules as above: one finished run per task and repeat, and
a record that is not a result (here five Forge runs our credit cut off) is kept apart and its run made again.

**Why Forge's side runs 4b21037.** The comparison started with 30eb649. Its first Forge runs showed a bug that Claude had
never triggered: Forge read every word of the request to decide whether the task builds a browser UI, and the polyglot
exercises link to Python's documentation (`errors.html`) and some describe games ("Score a bowling game"). Forge then
offered the browser build and playtest tools and waited on browser evidence before finishing; Astra followed that
contract and playtested Python classes (py_bowling: 1,035 s and $1.27, where Claude needed three calls). Forge's runner
was stopped after 40 runs (kept as `runs/2026-10-17_small_forge-30eb649_astra_stopped`, not counted), the fix was
made (table above, with a test) and checked on the three exercises
(`runs/2026-10-17_polyglot_forge-4b21037_astra_devcheck`, not counted), and Forge's side was run again from the start on
4b21037. Codex's runs were not touched. With Claude the fix changes only which tools are offered (on 19 polyglot
exercises and 14 SWE-bench instances, and Claude used none of them in any run), so the comparison with Claude Code stays on 30eb649.

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
| `official` | The comparisons: `rift-bench` 30eb649 against Claude Code (two repeats on the small tasks, one run per SWE-bench instance), and `rift-bench` 4b21037 against Codex on GPT-6 Astra (`"comparison": "astra"` in `run.json`). Earlier official builds (585ff1b) are kept as `exploratory`. |
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
