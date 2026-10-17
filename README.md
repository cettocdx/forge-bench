# Forge vs Claude Code and Codex

**The same model, the same tasks, the same hidden tests.** This repository compares
[Forge by Cogniphic Superintelligence](https://cogniphic.com/forge), a coding agent for the Mac,
with Claude Code, both running Claude Opus 5.5 at medium reasoning effort, on 372 programming tasks: real GitHub
issues in real repositories (all 300 of SWE-bench Lite, the benchmark Aider reported on, and 10 hard SWE-bench
Verified issues: the large tasks) and the Forge set and Aider's polyglot exercises (the small tasks). Every ablation
(reasoning effort low, Claude Sonnet 5.5) is run on both agents too. It measures how often each agent's result passes
tests it never saw, and what it spends to get there: tokens, dollars, model turns and seconds.

A second comparison runs Forge and Codex on OpenAI's GPT-6 Astra, on the same small tasks and 50 of the GitHub issues.

Everything is here: the harness, the tasks, every run we made (including stopped runs and the development runs that
found Forge's problems), Forge's full conversation for each run, the setup of each run and a checksum for every
file. You can run both agents yourself.

## Results

<!-- results:start -->
On large tasks (real GitHub issues in real repositories, outside the development sample): Forge solved 268/290 and Claude Code 262/290; Claude Code costs **1.47×** as much per solved task ($0.159 against $0.234).

On all of SWE-bench Lite (Aider's benchmark): Forge solved 276/300 and Claude Code 273/300; Claude Code costs **1.48×** as much per solved task ($0.150 against $0.223).

On small tasks: Forge solved 124/124 and Claude Code 122/124; Claude Code costs **2.62×** as much per solved task ($0.043 against $0.113).

| Tasks | Agent | Accepted | Success (95% CI) | Cost / accepted | Cost / run | Input tok / run | Output tok / run | Turns | Median s |
|---|---|---|---|---|---|---|---|---|---|
| **Large tasks**: SWE-bench Lite without the development sample + hard Verified | Forge | 268/290 | 92.4% (89–95%) | $0.1588 | $0.1467 | 114,567 | 3,231 | 7.66 | 107 |
|  | Claude Code | 262/290 | 90.3% (86–93%) | $0.2337 | $0.2111 | 240,781 | 2,990 | 8.50 | 36 |
| **SWE-bench Lite, all 300** (Aider's benchmark) | Forge | 276/300 | 92.0% (88–95%) | $0.1504 | $0.1383 | 105,232 | 3,033 | 7.32 | 104 |
|  | Claude Code | 273/300 | 91.0% (87–94%) | $0.2228 | $0.2027 | 230,651 | 2,827 | 8.22 | 35 |
| SWE-bench Verified, hard (10) | Forge | 9/10 | 90.0% (60–98%) | $0.3454 | $0.3109 | 298,239 | 7,209 | 13.60 | 132 |
|  | Claude Code | 7/10 | 70.0% (40–89%) | $0.5705 | $0.3993 | 466,944 | 6,601 | 12.50 | 81 |
| SWE-bench Lite, the other 260 | Forge | 239/260 | 91.9% (88–95%) | $0.1527 | $0.1404 | 107,931 | 3,077 | 7.42 | 104 |
|  | Claude Code | 237/260 | 91.1% (87–94%) | $0.2216 | $0.2020 | 229,691 | 2,808 | 8.32 | 35 |
| SWE-bench Lite, fresh sample (20) | Forge | 20/20 | 100.0% (84–100%) | $0.1469 | $0.1469 | 109,001 | 3,243 | 7.80 | 122 |
|  | Claude Code | 18/20 | 90.0% (70–97%) | $0.2619 | $0.2357 | 271,874 | 3,559 | 8.80 | 49 |
| Fresh sample, never looked at (14) | Forge | 14/14 | 100.0% (78–100%) | $0.1471 | $0.1471 | 107,208 | 3,294 | 8.14 | 117 |
|  | Claude Code | 12/14 | 85.7% (60–96%) | $0.2664 | $0.2283 | 274,071 | 3,377 | 8.64 | 34 |
| Hard sample, never looked at (4) | Forge | 3/4 | 75.0% (30–95%) | $0.3522 | $0.2642 | 215,963 | 5,623 | 12.25 | 132 |
|  | Claude Code | 2/4 | 50.0% (15–85%) | $0.7751 | $0.3875 | 425,359 | 6,089 | 8.75 | 98 |
| SWE-bench Lite, development sample (20) | Forge | 17/20 | 85.0% (64–95%) | $0.1209 | $0.1028 | 66,386 | 2,248 | 5.50 | 98 |
|  | Claude Code | 18/20 | 90.0% (70–97%) | $0.1998 | $0.1799 | 201,908 | 2,352 | 6.30 | 34 |
| **Small tasks**: Forge set + polyglot | Forge | 124/124 | 100.0% (97–100%) | $0.0430 | $0.0430 | 18,336 | 1,282 | 2.73 | 21 |
|  | Claude Code | 122/124 | 98.4% (94–100%) | $0.1129 | $0.1111 | 88,203 | 1,359 | 3.95 | 17 |
| Forge set (20) | Forge | 40/40 | 100.0% (91–100%) | $0.0345 | $0.0345 | 15,904 | 951 | 2.80 | 21 |
|  | Claude Code | 40/40 | 100.0% (91–100%) | $0.0956 | $0.0956 | 86,758 | 1,073 | 4.35 | 13 |
| Forge hard set (8) | Forge | 16/16 | 100.0% (81–100%) | $0.0473 | $0.0473 | 24,017 | 1,421 | 4.00 | 34 |
|  | Claude Code | 16/16 | 100.0% (81–100%) | $0.1205 | $0.1205 | 106,207 | 1,524 | 4.75 | 18 |
| Polyglot · Python (34) | Forge | 68/68 | 100.0% (95–100%) | $0.0471 | $0.0471 | 18,430 | 1,443 | 2.40 | 19 |
|  | Claude Code | 66/68 | 97.1% (90–99%) | $0.1216 | $0.1180 | 84,817 | 1,488 | 3.53 | 17 |
| All tasks | Forge | 409/434 | 94.2% (92–96%) | $0.1221 | $0.1151 | 84,852 | 2,629 | 6.15 | 79 |
|  | Claude Code | 402/434 | 92.6% (90–95%) | $0.1955 | $0.1811 | 195,396 | 2,495 | 7.10 | 27 |

Official runs only, pooled from `runs/` and computed by `harness/summarize.py` on 2026-10-17. Every other run (earlier builds, ablations) is in `runs/` too; see `results/summary.json`.

### Forge and Codex on GPT-6 Astra

The same model (`openai/gpt-6-astra` through OpenRouter, medium effort) in Forge (`rift-bench` 4b21037) and in Codex (`harness/run_codex.py`), on the same tasks and hidden tests; see METHODOLOGY.md.

On 50 real GitHub issues: Forge solved 35/50 and Codex 37/50; Codex costs **1.57×** as much per solved task ($0.609 against $0.958).

On small tasks: Forge solved 113/124 and Codex 114/124; Codex costs **2.72×** as much per solved task ($0.131 against $0.355).

| Tasks | Agent | Accepted | Success (95% CI) | Cost / accepted | Cost / run | Input tok / run | Output tok / run | Turns | Median s |
|---|---|---|---|---|---|---|---|---|---|
| **50 GitHub issues**: fresh and hard samples + 20 of the rest of Lite | Forge | 35/50 | 70.0% (56–81%) | $0.6092 | $0.4265 | 146,856 | 1,684 | 9.74 | 103 |
|  | Codex | 37/50 | 74.0% (60–84%) | $0.9579 | $0.7089 | 251,506 | 2,150 | 12.04 | 51 |
| SWE-bench Lite, fresh sample (20) | Forge | 16/20 | 80.0% (58–92%) | $0.4464 | $0.3571 | 119,482 | 1,381 | 9.30 | 84 |
|  | Codex | 16/20 | 80.0% (58–92%) | $0.8172 | $0.6538 | 229,983 | 1,919 | 11.65 | 50 |
| SWE-bench Verified, hard (10) | Forge | 6/10 | 60.0% (31–83%) | $1.2341 | $0.7405 | 267,309 | 3,207 | 13.00 | 110 |
|  | Codex | 6/10 | 60.0% (31–83%) | $1.6038 | $0.9623 | 348,978 | 3,282 | 14.10 | 85 |
| SWE-bench Lite, 20 of the rest (seed 20261017) | Forge | 13/20 | 65.0% (43–82%) | $0.5212 | $0.3388 | 114,005 | 1,224 | 8.55 | 104 |
|  | Codex | 15/20 | 75.0% (53–89%) | $0.8497 | $0.6373 | 224,293 | 1,816 | 11.40 | 42 |
| **Small tasks**: Forge set + polyglot | Forge | 113/124 | 91.1% (85–95%) | $0.1307 | $0.1191 | 25,493 | 1,269 | 6.69 | 37 |
|  | Codex | 114/124 | 91.9% (86–96%) | $0.3551 | $0.3264 | 68,204 | 1,130 | 4.60 | 26 |
| Forge set (20) | Forge | 40/40 | 100.0% (91–100%) | $0.0759 | $0.0759 | 20,360 | 661 | 6.10 | 31 |
|  | Codex | 40/40 | 100.0% (91–100%) | $0.2948 | $0.2948 | 68,711 | 693 | 5.17 | 19 |
| Forge hard set (8) | Forge | 16/16 | 100.0% (81–100%) | $0.1165 | $0.1165 | 29,847 | 1,144 | 7.69 | 43 |
|  | Codex | 16/16 | 100.0% (81–100%) | $0.3290 | $0.3290 | 69,105 | 1,189 | 5.25 | 26 |
| Polyglot · Python (34) | Forge | 57/68 | 83.8% (73–91%) | $0.1731 | $0.1451 | 27,489 | 1,656 | 6.81 | 39 |
|  | Codex | 58/68 | 85.3% (75–92%) | $0.4039 | $0.3445 | 67,694 | 1,373 | 4.12 | 29 |
<!-- results:end -->

## What's in here

| Path | What it is |
|---|---|
| `tasks/` | The Forge task set (`rift-28.json`) and how to build the polyglot set ([tasks/README.md](tasks/README.md)) |
| `harness/run_claude.py` | Runs Claude Code headless (`claude -p`) on a task file and judges each run with the hidden tests |
| `harness/run_codex.py` | Runs Codex headless (`codex exec`) the same way, on any OpenRouter model, so Forge can be compared with Codex on one model |
| `harness/polyglot_tasks.py` | Builds the polyglot Python tasks from Aider's benchmark at a pinned commit, and checks each one |
| `harness/swe_tasks.py` | SWE-bench: the seeded samples (Lite; Verified's hard instances), repositories at their base commits, and grading with the official harness |
| `harness/summarize.py` | Turns `runs/` into `results/summary.json` (what the benchmark page shows) |
| `harness/check_runs.py` | Checks that no counted run of either agent has an infrastructure error (`results/integrity.txt`) |
| `harness/report.py` | A quick table from any result files |
| `runs/<id>/` | One folder per run: `results.jsonl` (verbatim), `meta.json` (setup), `run.json` (label, kind) and, for Forge, `traces/` (each run's conversation) |
| `results/summary.json` | Every run aggregated, plus the official comparisons (`official`: with Claude Code; `comparisons.astra`: with Codex) |
| `MANIFEST.sha256` | SHA-256 of every file under `tasks/`, `runs/` and `results/` |
| `METHODOLOGY.md` | The protocol, the measures and the limits |

Forge's runner, `rift-bench`, is on the [releases page](../../releases): a build of Forge's Rust core that runs tasks
with no interface, the exact build the official Forge runs used (its version names the source commit): `rift-bench-30eb649`
for the comparison with Claude Code, `rift-bench-4b21037` (30eb649 and one fix, see METHODOLOGY.md) for the one with Codex. It uses your
own OpenRouter key, held in memory only. It is not notarized: check its SHA-256 against the release, then remove the
quarantine flag macOS puts on downloads. If you stop this build mid-run it can leave its `rift-egress-proxy-*`
container running in Docker; later builds remove their sandbox when stopped.

## Run it yourself

You need Docker, [Claude Code](https://docs.claude.com/en/docs/claude-code) signed in, Python 3.10+ and an
[OpenRouter](https://openrouter.ai) key. A full run of both agents (62 tasks, two repeats each) costs a few dollars.

```bash
# 1. check that every recorded file is unchanged, and that no counted run has an infrastructure error
shasum -a 256 -c MANIFEST.sha256
python3 harness/check_runs.py

# 2. build the polyglot tasks and check you have the same set
git clone https://github.com/Aider-AI/polyglot-benchmark /tmp/pb && git -C /tmp/pb checkout 7e0611e
python3 harness/polyglot_tasks.py /tmp/pb --check --out tasks/polyglot-py.json
(cd tasks && shasum -a 256 -c polyglot-py.sha256)

# 3. Claude Code
mkdir -p mine
python3 harness/run_claude.py --tasks tasks/rift-28.json --reps 2 --out mine/claude.jsonl
python3 harness/run_claude.py --tasks tasks/polyglot-py.json --reps 2 --out mine/claude.jsonl

# 4. Forge (rift-bench-macos-arm64 from the releases page; macOS on Apple silicon)
shasum -a 256 -c rift-bench-macos-arm64.sha256
mv rift-bench-macos-arm64 rift-bench && chmod +x rift-bench && xattr -d com.apple.quarantine rift-bench
./rift-bench --version
export OPENROUTER_API_KEY=...
./rift-bench run --tasks tasks/rift-28.json --tasks tasks/polyglot-py.json --reps 2 --out mine/forge.jsonl

# 4b. SWE-bench Lite (official harness; each instance's evaluation image is ~4 GB, pulled and removed one at a time)
python3 -m venv .venv && .venv/bin/pip install swebench==5.0.2
.venv/bin/python harness/swe_tasks.py prepare --repos /tmp/swe-repos
python3 harness/run_claude.py --tasks tasks/swe-lite.json --repos /tmp/swe-repos --timeout 3600 --out mine/claude-swe.jsonl
./rift-bench run --tasks tasks/swe-lite.json --repos /tmp/swe-repos --deadline-s 3600 --out mine/forge-swe.jsonl
.venv/bin/python harness/swe_tasks.py evaluate "Forge=mine/forge-swe.jsonl" "Claude Code=mine/claude-swe.jsonl" --repos /tmp/swe-repos

# 4c. the hard SWE-bench Verified instances: the same steps with tasks/swe-verified-hard.json
.venv/bin/python harness/swe_tasks.py prepare --tasks tasks/swe-verified-hard.json --repos /tmp/swe-repos

# 5. compare
python3 harness/report.py "Forge=mine/forge.jsonl" "Claude Code=mine/claude.jsonl"
```

To compare Forge with Codex instead, give both agents the same OpenRouter model. `run_codex.py` runs each task in a
fresh project with a fresh, empty `CODEX_HOME` (no user config, `AGENTS.md`, skills, plugins or MCP servers), Codex's
sandbox on and its host integrations off. Codex reports tokens, not cost, so a run's cost is its tokens at the model's
OpenRouter list prices, kept in the meta file. Codex reads files only through its shell, so on tasks that disable
commands its shell stays on; those records say `shell_kept`.

```bash
export OPENROUTER_API_KEY=...
./rift-bench run --tasks tasks/rift-28.json --model openai/gpt-6-astra --out mine/forge.jsonl
python3 harness/run_codex.py --tasks tasks/rift-28.json --model openai/gpt-6-astra --out mine/codex.jsonl
python3 harness/report.py "Forge=mine/forge.jsonl" "Codex=mine/codex.jsonl"
```

To add your runs to the record, put each in `runs/<date>_<what>/` with `results.jsonl`, its `.meta.json` renamed to
`meta.json` and a `run.json`, then run `harness/summarize.py`, `harness/readme_results.py` and regenerate the manifest:
`find tasks runs results -type f ! -name '*.md' ! -name polyglot-py.json | sort | xargs shasum -a 256 > MANIFEST.sha256`.

## How it works, briefly

- Each run starts in an empty folder with only the task's files. Claude Code gets no settings, MCP servers, skills or
  session history; Forge gets a fresh data directory. Both receive the task's request text unchanged.
- The hidden tests are never in the agent's folder. After the agent stops, they run on its final tree in a container
  with no network, with the same command for both agents.
- Cost counts every model call of a run, repairs and failed runs included. Forge's figure is what OpenRouter charged;
  Claude Code's is the `total_cost_usd` it reports (Anthropic list prices).

The full protocol, every measure's definition and the limits are in [METHODOLOGY.md](METHODOLOGY.md).

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE). The polyglot tasks are built from Exercism exercises
(MIT) via Aider's polyglot benchmark and are not redistributed here. Claude and Claude Code are trademarks of
Anthropic, PBC; this benchmark is independent and not affiliated with or endorsed by Anthropic.
