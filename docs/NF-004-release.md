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
- The macOS app is signed with the certificate in the repository's secrets when they're set (macOS then keeps
  its permissions across releases), else ad hoc; either way it's verified. `packaging/signing-cert.sh` makes
  that certificate once (self-signed, 20 years) and says which secrets to add.
- `test.yml` runs the Python tests and the TypeScript check on macOS 15 and Windows for each push to main;
  `release.yml` builds on both.
- Push a `v*` tag for a release that carries both installers; run it by hand for a test build.

## Limits
- Not signed by a developer ID: macOS needs `xattr -cr`, Windows shows SmartScreen.
- No Intel macOS build in CI, and no Linux installer.
