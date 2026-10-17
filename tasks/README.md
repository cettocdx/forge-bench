# Task sets

| File | Tasks | What they are |
|---|---|---|
| `rift-28.json` | 28 | 20 tasks from Forge's own benchmark (8 tuning, 12 held out) and 8 harder held-out tasks: bug fixes, features, a 200-file repository, a symptom-only bug report, a concurrent user edit, a compatible multi-file rename. Node.js and Python. |
| `swe-lite-test.json` | 20 | The fresh sample of [SWE-bench Lite](https://www.swebench.com) (seed 20261014, none from the development sample): real GitHub issues in Django, SymPy, pytest, scikit-learn, Matplotlib and Flask. |
| `swe-lite-rest.json` | 260 | The rest of SWE-bench Lite: the 260 instances in neither 20-instance sample, so the three Lite files together are all 300. |
| `swe-verified-hard.json` | 10 | Hard instances of SWE-bench Verified (seed 20261015): of the 45 its annotators estimate take an engineer one to four hours or more, none from the Lite samples. Astropy, Django, pylint, pytest, Sphinx, SymPy. |
| `swe-lite-rest-20.json` | 20 | A sample of `swe-lite-rest.json` (seed 20261017, `sympy__sympy-17630` left out as it is also a hard instance), drawn before any run on it: with the fresh and hard samples it is the 50-instance set of the comparison with Codex on GPT-6 Astra. |
| `swe-lite.json` | 20 | The development sample of SWE-bench Lite (seed 20261013): Django, SymPy, Matplotlib, pytest and Sphinx. Forge's problems on large repositories were found and fixed on it (see METHODOLOGY.md). |
| `polyglot-py.json` | 34 | The Python half of [Aider's polyglot benchmark](https://github.com/Aider-AI/polyglot-benchmark) (Exercism exercises). Not stored here: build it, then check its hash. |

The SWE-bench tasks carry the issue as the request and the repository and commit in `swe`; their repositories are
prepared and their patches graded by the official SWE-bench harness (`harness/swe_tasks.py`). Every other task has
the project's starting files, the request the agent receives, a reference
solution, and hidden acceptance tests. The agent never sees the hidden tests; they judge its final
tree in a container with no network.

## Building the polyglot set

```bash
git clone https://github.com/Aider-AI/polyglot-benchmark /tmp/polyglot-benchmark
git -C /tmp/polyglot-benchmark checkout 7e0611e
python3 harness/polyglot_tasks.py /tmp/polyglot-benchmark --check --out tasks/polyglot-py.json
(cd tasks && shasum -a 256 -c polyglot-py.sha256)
```

`--check` runs every task twice before keeping it: the hidden tests must fail on the starting
stub and pass with the exercise's own example solution.

## Schema

Each task is one JSON object: `set`, `id`, `held_out`, `request`, `allow_exec` (whether the agent
may run commands), `node`, `files` / `reference` / `hidden` as `[path, content]` pairs,
`concurrent_edit` (a file the "user" changes three seconds into the run, or null), and
`acceptance` (`image` and `command` for the hidden tests).
