# Debugging the challan workflow

The browser runs headlessly by default. To show Chromium and enable Playwright
Inspector, set `PWDEBUG=1` before starting Python (the browser starts at import):

```bash
DEBUG_MODE=1 PWDEBUG=1 uv run python src/cli/cli.py workflow challan
```

Provide the usual workflow options or answer the prompts. `PWDEBUG=1` enables
the Playwright Inspector; `DEBUG_MODE=1` records a trace in `data/artifacts/`.
Open the printed trace path with:

```bash
uv run playwright show-trace data/artifacts/<trace-filename>.zip
```

Failures also save a screenshot in `data/artifacts/` when possible. The page
URL and HTTP status are logged after navigation. Screenshots and traces may
contain form data; they are ignored by Git under the existing artifacts rule.
Artifact filenames include the Prefect flow run name and ID; CAPTCHA images are
also saved there by default.

## Search and email a challan

```bash
uv run playwright-workflows search-challan VID260174142
```

The command searches Rajkosh, saves a PDF, uploads it using the `gcs-bucket`
Prefect block, and emails the PDF using the `resend-api-key` Secret. The default
recipient is `vinaymavi@gmail.com`; override it with `--recipient`. The default
sender is `onboarding@resend.dev` for testing; use `--sender` with an address on
a verified Resend domain when appropriate. A printed copy may represent a
pending transaction; check its payment status rather than assuming it is paid.

## Automatically look up created challans

With the Prefect server running (or connected to Prefect Cloud), register the
deployments and Automation once, using an existing process work pool:

```bash
uv run python scripts/deploy_challan_automations.py <work-pool-name>
```

Run a Prefect worker for that pool to execute the scheduled runs:

```bash
uv run prefect worker start --pool <work-pool-name>
```

The worker must run on a machine with access to this project at the same path,
its dependencies, Playwright Chromium, and the Prefect blocks used by the manual
lookup. The deployment script exits after registration; it does not run a server.
When the generation flow finds a challan number, it emits a Prefect event. The
Automation starts the scheduler, which schedules the lookup two minutes later.
The lookup uploads the PDF and emails the default recipient. A repeated event
for the same challan uses the same idempotency key and does not create another
lookup run. Prefect must be available when the event is emitted; if emission
fails, the payment flow logs the challan number for a manual lookup.

The delay does not confirm payment. The emailed challan may still show a pending
transaction; this automation does not poll for a later payment status.
