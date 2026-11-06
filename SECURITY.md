# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Use GitHub's
private reporting instead: *Security → Report a vulnerability* on this
repository. Include the plugin version (`/crew-version`), your OS, and the
smallest reproduction you can.

You can expect an acknowledgement within a few days. This is a small
community-maintained project: fixes are best-effort, and we credit reporters
who want it.

## Supported versions

Only the latest release on `main` receives fixes.

## What crew-mates does on your machine

Knowing this helps you judge a report (and the plugin itself):

- **Hooks run locally** (`PreToolUse`, `Stop`, `SessionStart`, `SessionEnd`,
  `PostToolUse`) as Python scripts from the plugin directory. They read and
  write files under your project's `crew/` folder and run `git` commands
  (`git mv`, `git worktree`, the closure auto-commit). They never send data
  anywhere.
- **No network access by default.** The only network traffic is the optional
  team mode (`/crew-collab on` / `remote_claims : true`), which pushes a
  dedicated ref, `refs/crew/claims`, to your own git remote with your own
  credentials. It never pushes `main` or your code.
- **No telemetry, no accounts, no hosted service.**
- **The optional dashboard** (`/crew-dashboard`) is a local web server bound to
  `127.0.0.1`; it has no authentication, so do not expose its port.
- **TypeScript mods** run in Claude Code's sandboxed mod runtime and only use
  the declared `$` API (file reads/writes, env reads, UI). They make zero LLM
  calls.

## Hardening tips

- Review `hooks/hooks.json` and `scripts/*.py` before installing any plugin,
  this one included.
- Names entered in `/crew-collab on` are validated (`[\w .@-]{1,60}`) because
  they end up in a config line, a claim, and a shell argument.
