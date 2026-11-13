# Debugging the challan workflow

The browser runs headlessly by default. To show Chromium and enable Playwright
Inspector, set `PWDEBUG=1` before starting Python (the browser starts at import):

```bash
DEBUG_MODE=1 PWDEBUG=1 uv run python src/cli/cli.py workflow challan
```

Provide the usual workflow options or answer the prompts. `PWDEBUG=1` enables
the Playwright Inspector; `DEBUG_MODE=1` records a trace in `data/artifacts/`
and enables interaction screenshots. Open the printed trace path with:

```bash
uv run playwright show-trace data/artifacts/<trace-filename>.zip
```

Failures also save a screenshot in `data/artifacts/` when possible. The page
URL and HTTP status are logged after navigation. Screenshots and traces may
contain form data; they are ignored by Git under the existing artifacts rule.
Artifact filenames include the Prefect flow run name and ID; CAPTCHA images are
also saved there by default.
