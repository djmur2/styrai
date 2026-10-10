# StyrAI Partner Demo — Start Here

This is a private, local demonstration of StyrAI's enterprise AI-governance
control plane. It uses fictional data and does not connect to an AI provider,
customer system, patient record or bank system.

**Partner build:** 0.2.0 · 10 October 2026

## What you need

- Python 3.11 or newer: <https://www.python.org/downloads/>
- A current web browser
- No cloud account, API key, installation package or third-party Python library

Unzip the package completely before starting it. Do not run the launch file
from inside the ZIP preview.

## Launch on macOS

1. Open the unzipped `StyrAI-Partner-Demo` folder.
2. Double-click **Start StyrAI Demo.command**.
3. Keep the Terminal window open while using the demo.

If macOS does not open the file on the first attempt, Control-click it, choose
**Open**, and confirm that you want to open this local script. Alternatively,
open Terminal in this folder and run:

```bash
python3 launch_styrai.py
```

## Launch on Windows

1. Open the unzipped `StyrAI-Partner-Demo` folder.
2. Double-click **Start StyrAI Demo.bat**.
3. Keep the Command Prompt window open while using the demo.

Terminal alternative:

```powershell
py -3 launch_styrai.py
```

If the Python Launcher is unavailable, use `python launch_styrai.py`.

## Launch on Linux

Open a terminal in the unzipped folder and run:

```bash
python3 launch_styrai.py
```

## Run the primary upload demonstration

The browser opens automatically on a local address such as
`http://127.0.0.1:8765/?presentation=1`. StyrAI checks ports 8765–8775 and
prints the exact address it selected.

1. Select **Reset demo**.
2. At **Upload synthetic CSV or JSON**, choose
   `samples/synthetic-credit-decisions.csv` from the unzipped package.
3. Confirm StyrAI shows the filename, parsed-record count, detected fields and a
   row preview. No result or compliance statistic should appear before this
   evidence is loaded.
4. Select **Upload .txt or .md** and choose
   `samples/stricter-company-ai-policy.md`.
5. Read the regulation-library cards. They show the exact provision,
   source/version, applicability note, control mapping and official-source
   link separately from the company policy.
6. Select **Run governance assessment**, review the extracted rule shown in the
   confirmation dialog, and select **OK** to activate it. The supported clauses
   are drafted from the uploaded text and only the confirmed rules are applied
   to the run. Nothing is activated autonomously in the background.
7. In the results, find record `FIN-1002`. It passes the applicable regulatory
   control proxies but requires manual review under the stricter company policy
   because its confidence is below 80% and no completed review is recorded.
8. Point out the separate counts and exact row-level citation. A regulatory
   screen pass is not a legal opinion, and the internal review requirement
   remains binding.

Every displayed ratio has a visible denominator: records evaluated out of
records uploaded, regulatory control checks by result, and internal-policy
control checks by result. There is no overall “percent compliant” score. Missing evidence is
reported as insufficient or not evaluated, never silently counted as a pass.

For a narrated version and the three additional runtime control tests, open
`docs/DEMO_SCRIPT.md`.

## Optional quick control tests

Below the upload workbench, the original scenarios remain available:

1. In **Stop a data leak**, select **Intercept outbound AI request**. Confirm
   `BLOCKED BEFORE PROVIDER`, `External model invoked: No`, and
   `Raw prompt stored: No`.
2. Select **Contain model drift**, then **Inject and contain drift**. Confirm
   drift changes from `0.06` to `0.27`, the model becomes guarded, and traffic
   is routed to a fallback.
3. Select **Flag control gaps**, then **Assess deployed AI system**. Confirm the
   observed and approved versions differ, a finding has an owner, and
   `Legal violation confirmed: No`.
4. Review **Correlated evidence** after each scenario.

## Stop the demo

Return to the Terminal or Command Prompt window and press **Ctrl+C**. Closing
only the browser tab does not stop the local server.

## Troubleshooting

- **The browser did not open:** use the local address printed in the launch
  window.
- **Python is too old:** install Python 3.11 or newer, reopen the terminal and
  try again.
- **A port is occupied:** the launcher checks eleven local ports automatically.
  If all are occupied, close one of the applications using ports 8765–8775.
- **A message says the local engine is older or incompatible:** your CSV or
  JSON is not the cause. Close every earlier StyrAI Terminal or Command Prompt
  window, then launch this package again. The launcher now verifies the
  upload-governance API before it reuses a running local server.
- **The screen shows an earlier result:** select **Reset demo**.
- **Test the package:** run `python3 -m unittest discover -s tests -v` on macOS
  or Linux, or `py -3 -m unittest discover -s tests -v` on Windows.

## Demonstration boundary

Dataset parsing, deterministic policy and regulatory-proxy decisions,
sensitive-data detection, model checks, findings, incidents and hash-chained
evidence execute locally. The prototype does not call an LLM or external model.
It extracts a conservative set of supported policy clauses into drafts and
requires the user-initiated run to activate them.

A production system could use an LLM to propose structured clauses and retrieve
supporting passages from long policies, but a named policy owner should approve
each interpretation, version and applicability decision before activation. The
runtime should evaluate those approved rules deterministically; an LLM should
not be the compliance judge.

Enterprise identity, browser or API interception, production telemetry,
model-provider calls, ticket delivery and customer data are simulated. This
package is not legal advice, a compliance certification or production software.

Use fictional demonstration data only.
