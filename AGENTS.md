# Balloon Pop Game

Sterling's fork (`sgbaird/balloon-pop-game`) of `nachman8/balloon-pop-game`, a projector-and-camera AR game: players
throw blue and yellow physical balls at a projected surface to pop virtual red and green balloons. `README.md`
covers the game itself (modes, power-ups, calibration, controls).

- `origin` is the fork; `upstream` is nachman8's repository. Branches, issues and pull requests go to the fork
  (`gh ... -R sgbaird/balloon-pop-game`), never upstream, unless Sterling says otherwise.
- Upstream maintainers must not be able to push to the fork. A pull request from the fork to upstream gets "Allow
  edits by maintainers" by default, which lets them push to its head branch here; any such pull request is opened
  with `gh pr create --no-maintainer-edit`, and its `maintainer_can_modify` is checked to be `false` afterwards.
- Python with OpenCV, NumPy, pygame and PyYAML (`pip install opencv-python numpy pygame pyyaml`). No
  `requirements.txt` and no tests yet.
- `main.py` is the entry point (camera thread, ball detection, Kalman tracking) and drives `game.py` (game logic and
  rendering). `CalibrationWizard.py` writes the YAML calibration files (`calibration.yaml`, `ball_calibration.yaml`,
  `projector_calibration.yaml`). `config-system.py` has a hyphen in its name, so it cannot be imported as a module.
- `main.py` imports `video_recorder`, which is not in the repository; the README lists it but it was never committed.
- The game needs a camera, a projector and a display, so a CI runner cannot play it. Check changes with
  `python -m py_compile *.py` and by reading the code, and say what was not run.
- The `.wav` and `.mp3` files are game sounds; leave them alone unless the task is about sound.

## @codex on GitHub

`@codex` (`.github/workflows/codex.yml`) in an issue (title or body) or an issue or PR conversation comment starts
a Codex session, for anyone with write access. Model and effort tags: `@codex+gpt-6-luna:high`, `@codex:low`; a bare
tag uses the plan's defaults. Efforts: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `ultra` (each model
accepts a subset). The first tag with a `+model` or `:effort` wins, wherever it is in the title or body. On an issue the session works on a new `codex/issue-<n>-<run>` branch and links a
compare page; on a PR it pushes to the PR's branch.

## The shared Codex login (for Sterling and for sessions)

Every run uses one ChatGPT-managed login (`auth.json`), following
https://learn.chatgpt.com/docs/auth/ci-cd-auth for ephemeral runners. Same design as
`ME-EN-250/me-en-250-private`, with its own separate login.

- `.github/actions/codex-run` restores the newest encrypted copy from the Actions cache (key prefix `codex-auth-`),
  falling back to the `CODEX_AUTH_JSON` secret, and saves a new encrypted copy whenever Codex rewrote the file.
  `CODEX_AUTH_KEY` is the encryption passphrase. No token with secret-write access is involved.
- `codex-keepalive.yml` forces a refresh on Mondays and Thursdays. Codex itself refreshes only within 5 minutes of
  the 10-day access token's expiry (or on a 401), so ordinary runs never refresh and can run in parallel.
- This repository is public: GitHub turns off scheduled workflows after 60 days with no repository activity. If the
  keep-alive stops, re-enable it under Actions and reseed.
- Sessions: never read, print or copy anything under `$CODEX_HOME`.
- **Reseed** if a run fails with "Reseed CODEX_AUTH_JSON", or the keep-alive fails twice in a row. On Sterling's
  PC, in PowerShell: `$env:CODEX_HOME="$env:USERPROFILE\.codex-ci-balloon"; npx -y @openai/codex@0.165.0 login`,
  then `gh secret set CODEX_AUTH_JSON -R sgbaird/balloon-pop-game < $env:USERPROFILE\.codex-ci-balloon\auth.json`,
  delete the cache entries (`gh cache delete --all -R sgbaird/balloon-pop-game`), run the keep-alive by hand
  (`gh workflow run codex-keepalive.yml -R sgbaird/balloon-pop-game`), and then delete the local `auth.json`. Never
  use that CODEX_HOME for local work, and never reuse another repository's CI login: the CI copy rotates its
  tokens, and two holders of one login log each other out.
