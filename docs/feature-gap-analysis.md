# Feature Gap Analysis

This document tracks what is already shipped, what is still worth building, and what this project intentionally does not implement.

## Shipped through v0.8.0

- Desktop shell with environment detection and settings persistence
- UE4SS bridge deployment
- Runtime diagnostics and preset scans
- Release packaging and GitHub release automation
- Searchable `ClientCheatCommands` asset catalogs
- Host command deck and command composer
- Runtime scan bookmarks for client-safe repeated scans
- Session log monitor and parsed client-side summaries
- Node 24-ready GitHub Actions workflow updates

## High-value features still unfinished

### Client-safe enhancements

- Live session dashboard for player position, biome, temperature, and nearby scan summaries
- Saved runtime scan bookmarks with one-click replay
- Session log viewer with filter and export tools
- Map-oriented bookmarks for manual coordinate workflows
- Richer local-only discovery panels for spawners, NPCs, drops, and bosses

### Host or solo enhancements

- Bulk inventory macros built on top of catalog search and composer presets
- Technology unlock packs grouped by progression phase
- Spawn bundles for repeatable testing scenarios
- Travel preset library for boss arenas, dungeons, and farming routes
- Import and export of user-defined command preset collections

### Build and release improvements

- Better release notes generation from the actual feature set
- CI smoke tests for CLI commands such as `--search-assets` and `--compose-host-command`
- Artifact verification step that checks release checksum values in CI
- Workflow modernization beyond action versions, such as explicit runner compatibility checks

## Intentionally out of scope

- Server authority bypass
- Permission escalation against multiplayer hosts
- Anti-cheat evasion
- Hidden admin or moderation bypasses

The project should continue to focus on client-visible tooling and host or solo workflows that stay within the local game and mod environment.
