# NF-004 Installers and releases

| Status | Area | Code |
| --- | --- | --- |
| 🟡 Needs polish | Getting started | `packaging/build.sh`, `packaging/proki-engine.spec`, `.github/workflows/release.yml` |

A macOS `.dmg` and a Windows installer, built by CI from a version tag.

## How it works
- `packaging/build.sh` freezes the engine with PyInstaller, adds a checksum-checked
  `nats-server`, then builds the app's installer for the OS it runs on.
- ActivityWatch's input watcher is frozen separately (its dependencies clash with the engine's)
  and shipped in the app; the launcher installs ActivityWatch if it's missing.
- The macOS app is ad-hoc signed and verified.
- CI runs the Python tests and the TypeScript check, then builds on macOS 14 and Windows.
- Push a `v*` tag for a release that carries both installers; run it by hand for a test build.

## Limits
- Not signed by a developer ID: macOS needs `xattr -cr`, Windows shows SmartScreen.
- No Intel macOS build in CI, and no Linux installer.
