# High refresh profile

Converted template releases run stock game logic at **120 Hz**, with **60 FPS**
output by default. Open **화면 설정** at the end of the in-game menu to select
40, 60 or 120 FPS. Confirm applies and saves the choice; cancel keeps it unchanged.
The renderer remains on the game thread and builds/draws the scene only when an
output frame is due. Movement and camera positions advance at 120 Hz.

## Conversion and API

```powershell
python -X utf8 -B scripts/migrate_project.py ORIGINAL NEW_COPY --data-encoding UTF-8 --widescreen --high-refresh
```

The option accepts only the reviewed stock sources, preserves the original
project and script IDs/order, and records timing patches in the migration
manifest. Widescreen is independent; omit it for a 640×480 high-refresh project.
Without `--high-refresh`, existing timing and the default 40 Hz remain intact.

The converted INI uses:

```ini
[Lunetile]
TimingProfile=stock120
RenderRate=60
```

- `Graphics.logic_rate` is read-only and returns 120 for this profile.
- `Graphics.frame_rate` is fixed at 120; assigning a different value raises
  `ArgumentError`. `Graphics.frame_count` counts 120 Hz game ticks.
- `Graphics.render_rate` reads/sets 40, 60 or 120. This changes output frequency,
  not gameplay speed; use the menu to persist it.
- Personal settings use an atomic replacement of `Saves/Lunetile/display.ini`.
  Missing, invalid or unreadable preferences leave the INI default active.
  A failed write preserves the previous setting and displays an error.

The converter adapts walking, jumping, scrolling, route/event waits, autonomous
movement decisions, battle phase/wait timing, timers, picture movement/rotation,
fog, dialogue fades and selection arrows. The runtime preserves the original
cadence of discrete route decisions, event starts and command-loop yielding so
their random calls and side effects do not multiply. The runtime preserves the
timing of flashes, battle effects, animations, window pulses and autotiles;
weather movement advances in smaller steps. Input is polled at 120 Hz while
held-key repeat delays retain their original real-time duration. Audio timing
and playback pitch are unchanged.

## Saves and compatibility

New stock120 saves carry version **2**, preventing older runtimes and legacy
timing projects from misreading their time units. Existing version 1 and original
import saves are supported. Loading scales elapsed ticks, the system timer,
active interpreter waits, movement/jump counters, fog and screen/picture durations
to 120 Hz exactly once. Spatial coordinates and turn-based battle counters are
not multiplied. Fractional movement uses serialized integer remainders, allowing
movement and jump state to resume without accumulating rounding drift.

Keep original saves/backups. Do not copy version 2 saves into an older runtime.
Custom scripts/plugins and arbitrary embedded frame-based script commands are
outside the verified stock conversion scope.

## Validation and diagnostics

CI checks output scheduling with a virtual clock (120 logic ticks producing
40/60/120 due frames), mode changes, resume/reset phase, dropped output and input
repeat cadence. Actual-launcher tests compare 40/120 Hz movement, jump, scroll,
event wait, timers, pictures, fog, flash/effect/animation durations, saved motion
state and legacy save conversion. They also test settings persistence, atomic
write failure and versioned save access.

The optional Release diagnostics ZIP's `verification.json` includes timing comparison values and two-second output
samples: target rate, elapsed seconds and changes in due/submitted/dropped/late
counts. These are successful DXGI submissions, **not physical monitor scans**.
Automated tests set the process-local `LUNETILE_TEST_BACKGROUND=1` flag to avoid
waiting for foreground focus. Normal games retain inactive-window pausing and
reset scheduling on resume, transitions and F12 restart.

The local stock story checks the actual settings scene at 60 and 120 FPS, save,
load, dialogue/choice, battle, map transfer and an ending using injected input,
then restarts the game to verify the saved FPS choice:

```powershell
python -X utf8 -B scripts/test_runtime_stock_boot.py NEW_COPY build/refresh-story --scenario --widescreen-checks --render-rate 120
```

Output waits use the swap chain's frame-latency handle. Busy/occluded output can
drop presentation frames while the logic loop continues. Hardware overload can
also miss the logic target; late ticks are recorded. A monitor below 120 Hz
cannot physically show 120 distinct frames per second. Extended play and
arbitrary games are not certified by these bounded tests.
