# Playable systems expansion

Approved: four families (warrior, mage, archer, rogue), first/second advancement;
one town, three fields, one boss map; level 1–30; ten quests; safe enhancement
(materials/currency consumed on failure, no destruction or downgrade).
Keep top-down four-direction movement, Windows Rust server, editable JSON,
separate Scripts.rxdata entries, original inputs and private accounts.

## Acceptance checklist

- [x] Translucent backgrounds, hover focus, readable foreground, draggable windows
- [x] Equipment instances, six slots, inventory, storage, atomic swapping
- [x] Skills/ranks/points, four jobs with two advancements, quickslot binding
- [x] Five playable maps/portals, ten quests, monsters and shared boss combat
- [x] Currency, shops, safe enhancement, loot
- [x] Two-party confirmed trade, parties, guilds
- [x] Legacy migration, journal recovery, malformed request/save-failure tests
- [x] Two real Windows clients with scripted system/combat/movement tests, physical UI/IME subset and foreground performance
- [x] Canonical folder/ZIP/hashes/docs updated; original/private data preserved

Implementation order: progression and item ownership, gameplay services,
multiplayer services, client windows/world, validation and release. The expanded release passed its automated and native scene checks and replaced the canonical output.
Equipment needs instance IDs so enhanced items retain their own enhancement in
inventory, storage and trade. Consumables keep the existing counted inventory.

Default progression: first advancement level 5, second level 20; one skill point
per character level including level 1. Basic attack is free. Existing burst rank
1 is retained during migration and consumes one point of the earned total.
All new definitions and balances live in JSON, not presentation code.

Completed 2026-10-24. See VALIDATION.md for evidence and boundaries: seeded level-25 native scenarios, no full natural progression/boss balance or two-PC LAN/endurance proof.
