# agentic-maintenance: an active-diagnosis test bed

A temperature alarm on the thrust bearing of a process pump can have four causes, and each calls
for a different intervention. Two of them, bearing wear and a drifting temperature sensor, produce
the same ramp on the historian. Telling them apart takes an action on the plant: a short speed
step, which costs production. This repository simulates that situation and asks a decision
question: when is a test worth its cost?

**Page (in French), with replayable agent runs:** https://pierrelux.github.io/agentic-maintenance/

The plant runs on NASA's [ProgPy](https://nasa.github.io/progpy/) centrifugal pump model. Agents
see what a reliability engineer sees (historian telemetry, an OEM manual, the site's
troubleshooting knowledge base, a maintenance log), can pay for a speed-step test or a technician
inspection, and must issue one work order. Every test advances plant time and is charged to a
ledger, and a missed cause is charged its consequence.

## The scenario

Pump **P-201** raises a *thrust-bearing temperature high* alarm (limit 72 °C). The cause is drawn
from the site's base rates:

| cause | prior | signature | right action | cost if missed |
|---|---|---|---|---|
| thrust-bearing wear | 30 % | Tt rises, oil rises slightly | replace bearing at a planned stop | 18 h unplanned stop and repair |
| RTD drift | 30 % | the reading drifts, the physics does not | replace the sensor | nuisance alarms, lost protection |
| oil-cooler fouling | 15 % | oil rises first and most | clean the cooler | oil-overheat trip |
| hot pump room | 25 % | everything tracks ambient | monitor | nothing |

On the history alone, wear and drift give the same smooth ramp on the same reading, and the small
oil-temperature rise that would betray wear is hidden by an unmeasured cooling-water disturbance.
Friction heat scales with the square of shaft speed while a sensor offset does not, so a 45-minute
step to 90 % speed separates them: the expected drops differ by about 1 °C, against 0.25 °C of
sensor noise.

## What is simulated, and what is not

* **Physics (ProgPy).** `CentrifugalPumpBase` from ProgPy 1.7.1 (Daigle and Goebel, 2013),
  integrated at 2 s and vectorised over scenarios. Wear enters through ProgPy's own thrust-friction
  state, fouling through its oil-cooling coefficient, a hot room through its ambient input.
* **Added on top.** Sensor drift (a bias with curvature on the Tt reading), unit-to-unit variation,
  diurnal and weather ambient, an Ornstein-Uhlenbeck cooling-water disturbance that the historian
  does not record, and measurement noise.
* **Synthetic documents.** The OEM manual (English), the site knowledge base (French, with base
  rates, past cases and reference costs) and a per-alarm maintenance log with hints that are
  informative but unreliable were written for this test bed (`maintsim/docs.py`). Costs are
  placeholders (`maintsim/config.py`).

## Policies

* `replace`: replace the bearing on every alarm.
* `inspect`: send a technician to the bearing, then act on what they find.
* `rules`: checks derived from the manual (Tt against ambient, oil against ambient), then `inspect`.
* `voi`: a myopic value-of-information policy on a reduced-order thermal model of the pump
  (`maintsim/twin.py`). Each hypothesis is linear-Gaussian in its continuous parameters given its
  onset time, so severities and unit offsets are integrated out in closed form and test outcomes
  have Gaussian-mixture predictive distributions. At each step it compares the expected cost of
  acting now with the expected cost after each test, plus the test's price.
* `oracle`: knows the cause, a lower bound on cost.
* LLM agents: any model driving the same tools through the CLI or the MCP server.

## Results

200 simulated alarms (seeds 1000 to 1199), reference costs:

| policy | mean cost per alarm | right cause |
|---|---|---|
| replace the bearing on every alarm | 55.7 k$ | 29.5 % |
| send a technician to the bearing | 47.9 k$ | 57.5 % |
| manual-derived rules, then technician | 12.4 k$ | 99.5 % |
| value-of-information policy | 10.6 k$ | 98.5 % |
| oracle | 9.5 k$ | 100.0 % |

The VOI policy runs the speed step on 104 of the 200 alarms and calls a technician on 16. Its 3 wrong causes are the same cheap hedge: cleaning the cooler on a hot-room alarm. The rules come close because they were written knowing the simulator.

### LLM agents

Eight further alarms (seeds 5001 to 5008) were given to Claude Haiku 5.5 (`claude-haiku-5-5`) and
Claude Sonnet 5.5 (`claude-sonnet-5-5`), zero-shot, each run once as a Claude Code subagent whose
only access to the plant was the CLI. The instructions are stored with each run in
`results/transcripts.json`.

| agent | right cause | mean cost per alarm |
|---|---|---|
| Claude Haiku 5.5 | 8 / 8 | 13.1 k$ |
| Claude Sonnet 5.5 | 7 / 8 | 43.0 k$ |
| VOI policy (same alarms) | 8 / 8 | 12.5 k$ |

Both models read the sources well. They differ from the VOI policy in the choice of test: on the
12 decisions where wear had to be separated from drift, they ran the speed step 4 times. The other
8 times they paid for a technician and an 8-hour wait, and when they gave a reason, it was that the
expected separation of about 1 °C looked too small to trust.

What is recorded for each LLM run:

* `results/llm_runs.json`: every tool call (arguments and the plant's answer) and the final action.
* `results/transcripts.json`: the instructions, the text the model wrote, every tool call and its
  result. Thinking blocks are not included. A few agents called tools outside the protocol that
  were available in the session (a clock, a reminder service); one reply from the reminder service
  carried account metadata and has been replaced by a note.
* `results/llm_reports/`: each model's final report.

## Reproducing

Python 3.10 to 3.12 (ProgPy 1.7.1 does not support 3.13).

```bash
uv venv -p 3.12 .venv
uv pip install -p .venv/bin/python "progpy==1.7.1" numpy "mcp[cli]"
export PYTHONPATH=.

# Reference policies on the 200-alarm benchmark and on the 8 LLM alarms (about 10 minutes)
.venv/bin/python scripts/benchmark.py --n 200 --seed0 1000 --set bench   # -> results/bench.json
.venv/bin/python scripts/benchmark.py --n 8 --seed0 5001 --set llm       # -> results/llm.json

# Regenerate the 8 LLM alarms and replay the recorded tool calls on them; every call must
# return exactly what the model saw
.venv/bin/python scripts/llm_runs.py rebuild                              # -> episodes/llm_<model>/

# Data for the page, then the page itself
.venv/bin/python scripts/export_replay.py                                 # -> results/replay.json
.venv/bin/python scripts/export_console.py                                # -> results/console.json
.venv/bin/python scripts/export_demo.py --showcase ep05001 --model haiku  # -> results/demo_data.json
.venv/bin/python demo/build_page.py                                       # -> docs/index.html
```

Episodes are generated deterministically from their seeds and are not committed (`episodes/`).
`scripts/export_transcripts.py` built `results/transcripts.json` from the Claude Code session
logs, which are not part of the repository.

## Running your own agent

Command line, one tool call per invocation:

```bash
.venv/bin/python -c "from maintsim.store import generate, ROOT; print(generate([42], ROOT/'mine'))"
MAINT_EPISODES=episodes/mine .venv/bin/python -m maintsim.cli ep00042 get_alarm
MAINT_EPISODES=episodes/mine .venv/bin/python -m maintsim.cli ep00042 run_speed_step_test '{"speed_pct": 90, "duration_min": 45}'
```

MCP server, for any MCP client:

```json
{"mcpServers": {"p201-plant": {"command": "/path/to/agentic-maintenance/.venv/bin/python",
  "args": ["-m", "maintsim.mcp_server"], "cwd": "/path/to/agentic-maintenance",
  "env": {"PYTHONPATH": "/path/to/agentic-maintenance"}}}}
```

Ask the agent to call `new_episode` and diagnose the alarm; `reveal_outcome` shows the hidden
cause and the cost ledger after the work order.

## Layout

```
maintsim/      simulator (plant.py), tools and ledger (env.py), documents (docs.py), costs (config.py),
               thermal model for the VOI policy (twin.py), policies (agents.py), CLI and MCP server
scripts/       benchmark, LLM-run export and replay, data exports for the page
results/       benchmark results, LLM runs, transcripts and reports, page data
demo/          page template and build script
docs/          the built page, served by GitHub Pages
```

## Limitations

One pump, one alarm, four causes chosen to be hard to separate on the history. Documents, base
rates and costs are synthetic. The rules and the VOI policy were written knowing the simulator, and
the VOI policy's thermal model shares its structure with the simulated plant, so their costs are
reference points, not estimates of what they would achieve on real equipment. The LLM results come
from eight alarms and one run per alarm. The open question is how much of the VOI policy's behaviour
an agent can learn without the hand-written model, from the documents and the data.

## References

* M. Daigle and K. Goebel. Model-based prognostics with concurrent damage progression processes.
  *IEEE Transactions on Systems, Man, and Cybernetics: Systems*, 43:535-546, 2013.
* R. A. Howard. Information value theory. *IEEE Transactions on Systems Science and Cybernetics*,
  2(1):22-26, 1966.
* NASA ProgPy: https://github.com/nasa/progpy

## License

MIT. Pierre-Luc Bacon, Université de Montréal (DIRO) and Mila.
