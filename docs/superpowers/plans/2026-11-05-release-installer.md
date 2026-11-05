# Release installer implementation plan

> **For agentic workers:** Use the approved design and execute in this session. Checkboxes track verified steps.

**Goal:** Install a pinned, verified release on a prepared PVE with recovery.

**Architecture:** A POSIX shell installer validates an explicitly named release archive and checks its checksum, preflights the PVE service dependencies, backs up the three destination files, installs and verifies their content, and restores them on write failure. A separately published checksum enables verification before execution.

**Tech Stack:** POSIX shell, Python 3, systemd, GitHub Releases.

**Spec:** `docs/superpowers/specs/2026-11-05-release-installer-design.md`

## Global constraints

- No automatic backup, scheduler, secret or webhook changes.
- Abort before writes if both prerequisite services or PVE Notify are absent.
- User controls and pins release version and SHA-256; never execute unverified downloads.
- A backup preserves only three named files and their absence; rollback never changes other files.

## Review focus

- Invalid archive/checksum: no installation writes; test rejected checksum.
- Missing unit or dependency: no installation writes; test preflight.
- First install and update: backup records absent/existing state; test both.
- Mid-install error: originals recovered; inject failure and verify files.
- systemd reload/verification failure: recover and report error; exercise with stubbed systemctl.

### Task 1: Installer and tests

**Files:** Create `install.sh`, `tests/test-install.sh`; update `README.md`, `docs/install.md`, flow scope and contract.

- [x] Write isolated tests for invalid checksums, missing services, installation, and rollback; run and confirm failures.
- [x] Implement installer that validates version/checksum, archive contents, service prerequisites and destination; back up before writes and restore after failures.
- [x] Re-run tests and the existing report self-test.
- [x] Run a clean PVE VM rehearsal, including tests of delivery via PVE notification matcher; distinguish simulation from live PBS backup.
- [ ] Run flow checker and independent review for the exact candidate; publish a release only after checks and rehearsal.
