# Widescreen display

Converted template releases use a 1280×720 logical canvas at the original 40 Hz.
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

Actual 1280×720 title/map/menu/save/load/battle screenshots were inspected on a
96-DPI monitor with per-monitor-aware game windows. Physical high-DPI and
FHD/QHD/4K monitor switching, arbitrary games, and extended play are not certified.
RTP is still required and is not redistributed.
