# Widescreen display

Converted template releases use a 1280×720 logical canvas, 120 Hz logic and
selectable 40/60/120 FPS output (default 60). See [high refresh](HIGH_REFRESH.md).
Character sprites, icons and fonts retain their original pixel sizes. The renderer
fits that canvas into the window or monitor without changing its aspect ratio;
unused output space is black. FHD and 4K fit 720p at 1.5× and 3× respectively.
Nearest-neighbor sampling retains pixel edges; fractional scaling can make their
physical sizes uneven. QHD output uses a 2× fit.

## Converting a stock project

```powershell
python -X utf8 -B scripts/migrate_project.py ORIGINAL NEW_COPY --data-encoding UTF-8 --widescreen
```

Only the reviewed stock script collection is accepted. The converter records
every layout change in `migration/manifest.json` and preserves script IDs/order.
Original projects are never overwritten. Omitting `--widescreen` preserves the
original layout and 640×480 default. Use the actual source text encoding.

The wide profile expands map viewports, scrolling limits, menus, inventory lists,
equipment, shops, save slots, name entry, dialogue and battle status. Maps smaller
than the canvas are centered and clipped, with black margins. Title, game-over
and battle backgrounds fill their region with aspect-preserving center cropping.
Battlers, target arrows and animations use the expanded coordinate space. Event
pictures retain their script coordinates. Loading a save recenters the camera.

## Configuration and scripting

The converted `Game.ini` contains:

```ini
[Lunetile]
Width=1280
Height=720
```

The existing launcher's INI remains BOM-marked UTF-16. Window resizing/maximizing
changes output size, not the logical canvas. Alt+Enter toggles borderless full
screen on the current monitor and restores the previous window placement.
The starting window fits the monitor work area. Per-monitor DPI awareness is
requested before window creation; DPI messages update the window rectangle.

Ruby extensions are `Graphics.width`, `Graphics.height` and
`Graphics.resize_screen(width, height)`. Resize runs on the game thread,
recreates rendering surfaces and clears the frozen transition image. Each axis
must be 1–4096 and the total must not exceed 8,294,400 pixels. Invalid dimensions
raise `ArgumentError`; resource allocation failures raise `RGSSError`.
Existing sprites/windows/viewports are not automatically rearranged by this API;
resize between scenes and recreate their layout. The shipped stock-wide profile
targets 1280×720. Custom UI plugins require their own adaptation.

## Release template map

Template packaging expands only the converted `Map001.rxdata` from 20×15 to
40×23 tiles (1280×736 pixels). Existing tiles and the starting position (9,7)
are preserved. Added cells use the same ground tile 384 and empty upper layers.
The wide viewport fills 1280×720; the camera has no horizontal travel and up to
16 pixels of vertical travel. The original `template-xp/` and ordinary project
conversion are unchanged.

The converted system data version increases once so stock loading refreshes
maps held in older saves. Player coordinates, switches and inventory are retained;
stock map refresh resets transient map effects/events as it does after an editor
data-version change. New saves use the existing version 2 format.

The playable ZIP contains only project files, runtime, README and license notices.
The engine is named `Lunetile.dll`; the converted `Game.ini` selects it with
`Library=Lunetile.dll`. The original `RGSS104E.dll` is excluded. Keep the unchanged
`Game.exe` and use the converted INI; renaming a DLL alone does not update that
setting. RGSS function names, project/save formats and save paths are unchanged.
Reports, migration/map records, source/game hashes, dependency locks and the Ruby
patch are in `lunetile-template-xp-diagnostics.zip`, which is optional for playing.
`SHA256SUMS.txt` is a separate Release attachment covering both ZIPs. Development
documentation and historical records remain in the repository.

## Validation

The release CI runs Python regression tests, native FHD/QHD/4K fit calculations,
640×480 and configured 1280×720 launcher checks, scene-edge pixel/clipping
checks, logical resize/transition checks and actual window resize, maximize,
full-screen restoration and synthetic DPI-message checks. The report accompanies
the exact DLL as `verification.json`.

Local Windows 11 checks additionally ran the converted stock title, new game,
menu, save/load, dialogue/choice, battle, map transfer and ending scenario using
injected logical input. The wide fixture checks 26 stock window bounds, list row
counts, large-map camera limits and small-map centering:

```powershell
python -X utf8 -B scripts/test_runtime_stock_boot.py NEW_COPY build/wide-scenario --scenario --widescreen-checks
```

For the packaged 40×23 map, add `--map-checks --render-rate 120`. This walks to
all four corners using stock movement, attempts to leave the map, reads terrain
pixels at each screen edge, checks the 16-pixel scroll limit and renders a
separate 80×45 colored tilemap at multiple camera positions. It then continues
the settings/save/load/battle scenario. Use 40, 60 or 120 for the output mode.

Actual 1280×720 title/map/menu/save/load/battle screenshots were inspected on a
96-DPI monitor with per-monitor-aware game windows. Physical high-DPI and
FHD/QHD/4K monitor switching, arbitrary games, and extended play are not certified.
RTP is still required and is not redistributed.

### Local map expansion checks, 2026-10-19

The packaging change passed 57 Python tests, the existing Ruby/native geometry
and launcher checks, and actual-launcher stock scenarios at 40/60/120 FPS.
All four corners were reached using injected directions, outward movement was
blocked, each screen edge matched RTP terrain pixels, and camera travel stayed
at 0 horizontal / 0–16 vertical pixels. A separate 80×45 colored tilemap passed
camera and pixel checks at the top-left, bottom-right and center. Settings
persisted across restart; save/load, dialogue/choice and one-hit battle passed.
These are bounded injected-input tests, not manual gameplay or endurance tests.

An actual alpha.5 save containing the old 20×15 map loaded as 40×23 while
retaining player position (18,13), variable 1=7853, switch 3 and 123 gold.
The system data version changed from 83812228 to 83812229. All 19 selected
original template inputs remained unchanged; the game folder has 29 files and
the optional diagnostics folder has nine. License notice bytes are preserved.

Three-second steady-map measurements after warm-up gave 39.89 / 59.83 / 119.99
successful DXGI submissions per second for targets 40 / 60 / 120, respectively.
Logic remained approximately 120 Hz; dropped/late counts were zero. This local
test DLL's SHA-256 was
`0c7ad95771a91ce01270da36514e52085f20155eb1e405a4a4ff25f19f3375af`.
Each Actions build's own DLL hash and CI scope are in its diagnostics ZIP.

Local evidence is in ignored `build/map-cleanup-verification-native/`,
`build/map-cleanup-story40/`, `build/map-cleanup-story60/`,
`build/map-cleanup-visual/`, `build/map-upgrade.json` and
`build/map-cleanup-measure-fps.json`; these paths are not public attachments.
