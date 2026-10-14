# Forge vs Claude Code

**The same model, the same tasks, the same hidden tests.** This repository compares
[Forge by Cogniphic Superintelligence](https://cogniphic.com/forge), a coding agent for the Mac,
with Claude Code, both running Claude Opus 5.5 at medium reasoning effort, on 112 programming tasks: real GitHub
issues in real repositories (a fresh SWE-bench Lite sample and hard SWE-bench Verified instances, the large tasks),
a SWE-bench Lite development sample, the Forge set and Aider's polyglot exercises (the small tasks). Every ablation
(reasoning effort low, Claude Sonnet 5.5) is run on both agents too. It measures how often each agent's result passes
tests it never saw, and what it spends to get there: tokens, dollars, model turns and seconds.

Everything is here: the harness, the tasks, every run we made (including stopped runs and the development runs that
found Forge's problems), Forge's full conversation for each run, the setup of each run and a checksum for every
file. You can run both agents yourself.

## Results

<!-- results:start -->
On large tasks (real GitHub issues in real repositories): Forge solved 28/30 and Claude Code 25/30; Claude Code costs **1.49×** as much per solved task ($0.234 against $0.348).

On small tasks: Forge solved 123/124 and Claude Code 122/124; Claude Code costs **2.56×** as much per solved task ($0.044 against $0.113).

| Tasks | Agent | Accepted | Success (95% CI) | Cost / accepted | Cost / run | Input tok / run | Output tok / run | Turns | Median s |
|---|---|---|---|---|---|---|---|---|---|
| **Large tasks**: fresh SWE-bench Lite + hard Verified | Forge | 28/30 | 93.3% (79–98%) | $0.2337 | $0.2181 | 200,457 | 5,034 | 11.43 | 120 |
|  | Claude Code | 25/30 | 83.3% (66–93%) | $0.3483 | $0.2902 | 336,897 | 4,573 | 10.03 | 49 |
| SWE-bench Verified, hard (10) | Forge | 8/10 | 80.0% (49–94%) | $0.3852 | $0.3081 | 283,910 | 7,431 | 13.30 | 193 |
|  | Claude Code | 7/10 | 70.0% (40–89%) | $0.5705 | $0.3993 | 466,944 | 6,601 | 12.50 | 81 |
| SWE-bench Lite, fresh sample (20) | Forge | 20/20 | 100.0% (84–100%) | $0.1731 | $0.1731 | 158,730 | 3,835 | 10.50 | 111 |
|  | Claude Code | 18/20 | 90.0% (70–97%) | $0.2619 | $0.2357 | 271,874 | 3,559 | 8.80 | 49 |
| Fresh sample, never looked at (19) | Forge | 19/19 | 100.0% (83–100%) | $0.1760 | $0.1760 | 160,213 | 3,899 | 10.42 | 107 |
|  | Claude Code | 17/19 | 89.5% (69–97%) | $0.2686 | $0.2404 | 274,527 | 3,670 | 8.79 | 49 |
| SWE-bench Lite, development sample (20) | Forge | 17/20 | 85.0% (64–95%) | $0.1641 | $0.1395 | 119,499 | 3,199 | 8.90 | 124 |
|  | Claude Code | 18/20 | 90.0% (70–97%) | $0.1998 | $0.1799 | 201,908 | 2,352 | 6.30 | 34 |
| **Small tasks**: Forge set + polyglot | Forge | 123/124 | 99.2% (96–100%) | $0.0440 | $0.0437 | 20,131 | 1,321 | 2.90 | 20 |
|  | Claude Code | 122/124 | 98.4% (94–100%) | $0.1129 | $0.1111 | 88,203 | 1,359 | 3.95 | 17 |
| Forge set (20) | Forge | 40/40 | 100.0% (91–100%) | $0.0353 | $0.0353 | 18,168 | 970 | 3.08 | 22 |
|  | Claude Code | 40/40 | 100.0% (91–100%) | $0.0956 | $0.0956 | 86,758 | 1,073 | 4.35 | 13 |
| Forge hard set (8) | Forge | 16/16 | 100.0% (81–100%) | $0.0480 | $0.0480 | 24,732 | 1,533 | 4.00 | 23 |
|  | Claude Code | 16/16 | 100.0% (81–100%) | $0.1205 | $0.1205 | 106,207 | 1,524 | 4.75 | 18 |
| Polyglot · Python (34) | Forge | 67/68 | 98.5% (92–100%) | $0.0483 | $0.0476 | 20,204 | 1,478 | 2.53 | 18 |
|  | Claude Code | 66/68 | 97.1% (90–99%) | $0.1216 | $0.1180 | 84,817 | 1,488 | 3.53 | 17 |
| All tasks | Forge | 168/174 | 96.5% (93–98%) | $0.0878 | $0.0848 | 62,643 | 2,177 | 5.06 | 22 |
|  | Claude Code | 165/174 | 94.8% (90–97%) | $0.1580 | $0.1499 | 144,151 | 2,027 | 5.27 | 18 |

Official runs only, pooled from `runs/` and computed by `harness/summarize.py` on 2026-10-13. Every other run (earlier builds, ablations) is in `runs/` too; see `results/summary.json`.
<!-- results:end -->

## What's in here

| Path | What it is |
|---|---|
| `tasks/` | The Forge task set (`rift-28.json`) and how to build the polyglot set ([tasks/README.md](tasks/README.md)) |
| `harness/run_claude.py` | Runs Claude Code headless (`claude -p`) on a task file and judges each run with the hidden tests |
| `harness/polyglot_tasks.py` | Builds the polyglot Python tasks from Aider's benchmark at a pinned commit, and checks each one |
| `harness/swe_tasks.py` | SWE-bench: the seeded samples (Lite; Verified's hard instances), repositories at their base commits, and grading with the official harness |
| `harness/summarize.py` | Turns `runs/` into `results/summary.json` (what the benchmark page shows) |
| `harness/check_runs.py` | Checks that no counted run of either agent has an infrastructure error (`results/integrity.txt`) |
| `harness/report.py` | A quick table from any result files |
| `runs/<id>/` | One folder per run: `results.jsonl` (verbatim), `meta.json` (setup), `run.json` (label, kind) and, for Forge, `traces/` (each run's conversation) |
| `results/summary.json` | Every run aggregated, plus the official comparison |
| `MANIFEST.sha256` | SHA-256 of every file under `tasks/`, `runs/` and `results/` |
| `METHODOLOGY.md` | The protocol, the measures and the limits |

Forge's runner, `rift-bench`, is on the [releases page](../../releases): a build of Forge's Rust core that runs tasks
with no interface, the exact build every official Forge run used (its version names the source commit). It uses your
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

To add your runs to the record, put each in `runs/<date>_<what>/` with `results.jsonl`, its `.meta.json` renamed to
`meta.json` and a `run.json`, then run `harness/summarize.py`, `harness/readme_results.py` and regenerate the manifest:
`find tasks runs results -type f ! -name '*.md' | sort | xargs shasum -a 256 > MANIFEST.sha256`.

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
