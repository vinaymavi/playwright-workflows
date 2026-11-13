# Debugging the challan workflow

The browser runs headlessly by default. To show Chromium and enable Playwright
Inspector, set `PWDEBUG=1` before starting Python (the browser starts at import):

```bash
PWDEBUG=1 uv run python src/cli/cli.py workflow challan --pause --trace
```

Provide the usual workflow options or answer the prompts. `--pause` opens the
Inspector after the form loads; use its controls to step through the actions.
`--trace` saves a trace in `data/artifacts/`. Open it with:

```bash
uv run playwright show-trace data/artifacts/<flow-run-name>-<flow-run-id>-trace.zip
```

Failures also save a screenshot in `data/artifacts/` when possible. The page
URL and HTTP status are logged after navigation. Screenshots and traces may
contain form data; they are ignored by Git under the existing artifacts rule.
Artifact filenames include the Prefect flow run name and ID; CAPTCHA images are
also saved there by default.
