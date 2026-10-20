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

## Rendering performance

VXA Table objects track an instance identity, revision and the latest 64 cell changes without changing their Marshal bytes. Each Tilemap uses a native ring cache bounded by the visible tile range and 32 MiB. Pixel scrolling changes only the origin; tile scrolling refreshes entering rows/columns. Cell edits refresh affected tiles and table-edge dependents; history overflow, resized/replaced tables and flags changes refresh the visible range. A1 animation refreshes geometry without rereading map cells.

Tile geometry and sheet slots stay numeric: no Bitmap or GPU pointer is retained in the cache. Lower/upper batches expand directly to native draws using current bitmap contents and dimensions, preserving order and the 100,000-expanded-command limit. Sprites/windows keep their existing commands. Nonstandard Table/readers, bitmap subclasses and unsupported geometry use the previous Ruby tile path. Fully transparent Plane bitmaps skip drawing, and bitmap edits invalidate the transparency cache.

VXA native tile draws use 32-byte position/UV instances, uploaded with one WRITE_DISCARD per output frame. Only consecutive quads with the same bitmap, clip and blend within one lower/upper command share a DrawInstanced call. Textures are never sorted. Ordinary drawing restores the original shader/input layout. CPU/GPU instance stores each hold at most 100,000 instances (3,200,000 bytes); F12 resets usage and shutdown releases resources. XP retains its existing drawing path.

`Graphics.__timings` retains its existing fields. Internal diagnostic `Graphics.__render_parts` returns `[command_parse_ms, d3d_submit_ms]` for the last submitted frame; GPU timing remains asynchronous. These diagnostics measure successful DXGI submissions, not physical display scan-out.

VXA-only `Graphics.__tile_batches` returns `[tile_quads, tile_draws, regular_draws, constant_maps, instance_maps, capacity_bytes_each, before_present_ms, present_ms]` for the last render attempt. Draw/map counts are actual API calls, capacity is logical CPU/GPU storage rather than driver residency, and the two time intervals sum to the existing render_ms. These internal diagnostics are not supported RGSS APIs.

For sequential local comparison with the retained pre-cache DLL:

```powershell
python -X utf8 -B scripts/benchmark_runtime_vxa.py build/vxa-render-performance --baseline PATH_TO_BASELINE_LUNETILEVXA_DLL
```

The benchmark uses a disposable 40×23 starting map, idle/moving 30-second runs repeated three times per DLL, and 40/60FPS checks. It requires at least 118 submitted FPS at the 120FPS setting, 119–121Hz logic, no more than 2% missing output frames and command generation p95 at most 4ms. It also requires at least 30% lower mean command-generation-plus-parse time and 50% fewer Ruby allocations per presented frame, separately for idle and moving runs. GC time and cache reads/builds/bytes are recorded. This hardware-dependent performance gate is separate from CI correctness checks. See VALIDATION.md for the measured build and hashes.

For D3D submission changes, use `--profile tile-d3d` with the retained pre-instancing DLL. The default remains `tile-cache` with its original gates. The D3D profile requires 30% lower mean submission time, 10% lower mean generation+parse+submission time, at most 5% higher total p95 for every paired repeat, at least 90% fewer tile draws and no more than 5% additional Ruby allocations per output frame. It also compares three 10-second alternating-texture runs per DLL; their total mean and paired p95 must not regress by more than 5%. GPU samples are counted once per valid unique sequence and are never added to CPU time.

To update an existing alpha.10-or-later converted project, close the game and editor, back up the project, then replace only LunetileVXA.dll beside Game.exe using lunetile-vxa-speed-fix.zip. Data, Saves and Game.ini are not included in that patch.
