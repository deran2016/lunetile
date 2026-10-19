# Repository Guidelines

Lunetile is the public project name; retain legacy RGSSXP identifiers where required by runtime and save compatibility.

## Project Structure & Module Organization

- `src/runtime/`: C++17 engine, embedded Ruby compatibility code, ABI definitions, dependency locks, and patches.
- `scripts/`: PowerShell builds and Python migration, packaging, inspection, and profiling tools.
- `tests/`: Python unit tests, Ruby scenarios, and native probes.
- `tools/etw/`: optional Windows trace extractor.
- `docs/VALIDATION.md`: independent-build evidence; `docs/history/`: earlier implementation and acceptance records.
- `licenses/`: upstream notices. `build/`: ignored downloads, binaries, and local verification outputs.

`template/` is the user-supplied release project. Its launcher, project file, data, and game assets are the explicit exception to ignored game inputs. Never commit its original RGSS DLL, personal saves, logs, or unrelated proprietary files. Preserve template inputs; package only converted copies.

## Build, Test, and Development Commands

Run from the repository root on Windows. Use VS2022 C++ tools with the Windows SDK, CMake 3.24+, Python 3.12, and a Ruby 3.1+ bootstrap executable. Target Win32/x86.

```powershell
python -m pip install -r requirements-dev.txt
powershell -NoProfile -File scripts/build_runtime.ps1 -BaseRuby "BOOTSTRAP_RUBY_EXE"
python -X utf8 -B -m unittest discover -s tests -v
python -B scripts/inspect_runtime.py build/runtime-native/bin/Release/Lunetile.dll
```

These install development dependencies, build the runtime, run unit tests, and inspect DLL architecture/exports.

```powershell
python -B scripts/migrate_project.py "ORIGINAL_PROJECT" "NEW_PROJECT"
```

Use a nonexistent output directory, then run its `Game.exe`. Specify actual text encodings when required; see README.md. Never overwrite the original project.

## Coding Style & Naming Conventions

Match surrounding code: C++ commonly uses four-space indentation, Ruby two spaces, and compact Python tools often one space per nesting level. Avoid unrelated reformatting. Use snake_case filenames and descriptive `test_*` methods; retain RGSS API names and ABI contracts.

No repository-wide formatter or linter is configured. Follow `.gitattributes`: LF for listed source/document formats, CRLF for PowerShell, and unchanged upstream license bytes. Run `git diff --check`.

## Testing Guidelines

Python tests use `unittest` discovery with `tests/test_*.py`; Ruby scenarios and native probes cover runtime behavior. Add focused regression checks for changed logic, malformed input, and data preservation. No percentage coverage threshold is configured.

For native changes, rebuild and run relevant launcher/runtime checks. Record commands, results, and DLL hashes; distinguish automated checks from actual gameplay and historical evidence.

## Commit & Pull Request Guidelines

History currently contains `feat: publish standalone RGSSXP runtime`. Follow its concise, type-prefixed style, such as `fix: preserve imported saves`.

PRs should explain the problem, behavior change, validation, and remaining limits. Link relevant issues and include screenshots for visible rendering changes. Update affected documentation and packaging paths together. Review staged files to exclude generated outputs and private inputs.
