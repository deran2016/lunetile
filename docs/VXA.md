# VX Ace compatibility

Lunetile builds `LunetileVXA.dll` separately from the existing XP `Lunetile.dll`.
Both use the pinned x86 Ruby 4.0.7 runtime and shared native rendering, input and audio code.
The VXA target loads its own RGSS3 data classes, tilemap, windows, stock-script hooks and ABI.
Compatibility is limited to the supplied 126 stock scripts; arbitrary plugins and full-game compatibility are not certified.

## Convert a project

Run from the repository root after building both DLLs:

```powershell
python -X utf8 -B scripts/inspect_runtime.py build/runtime-native/bin/Release/LunetileVXA.dll --engine vxa
python -X utf8 -B scripts/migrate_project.py template-vxa build/vxa-original-layout --engine vxa
python -X utf8 -B scripts/migrate_project.py template-vxa build/vxa-wide --engine vxa --widescreen --high-refresh
```

Output directories must not exist and must be outside the original project.
Auto-detection is the default; conflicting project, INI and known-launcher identifiers are rejected.
The launcher hash, script names/order and every source hash must match the reviewed template.
Only Main receives the stock compatibility bootstrap. Untouched Marshal entries, including their encoding metadata and reference numbering, remain byte-for-byte identical.

Plain conversion keeps 544×416 and 60Hz. The flags select 1280×720 and a `stock120` timing profile with 60FPS output by default.
The original `RGSS301.dll` is excluded. The copied INI selects `Library=LunetileVXA.dll`.
`.rgss3a` v3 archives are indexed with bounds, path, duplicate and overlap checks; the converted scripts use a separate loose path.
Project data is inspected before publication; malformed Marshal, ambiguous encoding and unreviewed event Ruby stop conversion.

New saves use `Saves/LunetileVXA/`; original `SaveNN.rvdata2` files are copied to `Saves/Import/`.
Existing `Saves/` trees require review instead of silently merging incompatible formats.
Original projects and saves are never overwritten.

## Package

```powershell
python -X utf8 -B scripts/test_runtime_vxa.py build/ci-verification/vxa
python -X utf8 -B scripts/package_template_vxa.py template-vxa build/runtime-native/bin/Release build/lunetile-template-vxa-windows-x86 build/lunetile-template-vxa-diagnostics --zip
```

Packaging requires `verification-vxa.json` with a successful result matching the exact DLL SHA-256.
It converts a clean copy of the allowed template inputs, expands its starting map from 17×13×4 to 40×23×4, and preserves the original tiles, events and starting position `(8,6)`.
The System file is preserved. Original template files are hashed again before publication.

Outputs:

- `lunetile-template-vxa-windows-x86.zip`: converted project, launcher, new DLL and notices.
- `lunetile-template-vxa-diagnostics.zip`: native verification, migration record, map change and file SHA-256 manifests.

Extract the game ZIP and run `Game.exe`. Install RPG Maker VX Ace RTP and the Microsoft Visual C++ x86 runtime separately.
RTP, original engine DLLs, personal saves, logs and raw analysis artifacts are not distributed.
The VX Ace editor restores both `Library=System\RGSS301.dll` and its original DLL on save. The Main entry bootstrap detects that runtime, restores `Library=LunetileVXA.dll`, starts `Game.exe` once with the original test/battle-test flag, and exits the original process. The original editor-supplied DLL is neither modified nor distributed. A missing Lunetile DLL or a failed INI write/restart produces an explicit error.
For an existing alpha.9 project, back it up and download `lunetile-vxa-editor-fix.zip`. Insert its `LunetileEditorFix.rb` text into a new script entry immediately above Main using the VX Ace script editor (F11), then save. Keep `LunetileVXA.dll` beside `Game.exe`. The repair archive does not auto-install or contain Data/Saves; do not overwrite your edited project with the full template. Copying a DLL into System alone does not survive another editor save.
The supplied VX Ace launcher uses Unicode paths; Korean extraction paths are included in the native checks.

OGV playback includes a statically linked Theora decoder and Vorbis audio support, without a system codec installation.
Movie inputs are limited to 128 MiB and 4096 pixels per axis. Other video formats use installed Windows DirectShow decoders.

## Evidence boundaries

Focused Python tests cover Marshal metadata/reference preservation, pinned stock validation, conflicting engine identifiers, malformed archives and data, map-cell/event preservation, package filtering and ZIP content verification.
The map and data tests run the pinned Ruby executable when available; otherwise they report a skip.
The native harness records current DLL checks in `verification-vxa.json`; XP results and historical evidence do not certify a new VXA build.
Passing the harness does not by itself prove a complete gameplay campaign, every stock event, movie playback, visual/audio parity or arbitrary plugin compatibility.
See [VALIDATION.md](VALIDATION.md) and the generated report for performed checks and remaining limitations.
