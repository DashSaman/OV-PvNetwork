# PVNetwork Release Quality Gate

This file is blocking. A release is not publishable while any applicable item below is incomplete or unsupported by evidence.

## 0. Production safety — mandatory

- [ ] Treat Production as live and under load throughout the change.
- [ ] Development happened on an isolated branch/worktree, not directly in `/opt/ov-panel`.
- [ ] No blanket firewall flush, default-route replacement, unrelated service restart, destructive DB reset or unnecessary credential/certificate rotation occurred.
- [ ] A pre-deploy backup/check exists for every Production mutation.
- [ ] Only the smallest required service is restarted.
- [ ] Local/public health checks pass after deployment.
- [ ] A rollback path is known and tested enough for the change risk.

## 1. Automated correctness

- [ ] `python3 -m unittest discover -s tests -v` passes.
- [ ] `python3 -m compileall -q backend tests` passes.
- [ ] `npm ci && npm run build` passes in `frontend/`.
- [ ] JSON language files parse successfully.
- [ ] Existing renewal regression tests remain green.
- [ ] New behavior has a focused regression test before its task becomes `[x]`.

## 2. Responsive UI blockers

Release-visible admin and subscription flows must be checked at 360, 375, 390, 430, 768, 1024, 1366, 1440 and 1920 px.

- [ ] No page-level horizontal scroll caused by layout bugs.
- [ ] No required action is clipped or hidden behind fixed headers/bottom navigation.
- [ ] Modal content is viewport-bounded and internally scrollable where needed.
- [ ] Modal cancel/confirm controls remain reachable on short screens.
- [ ] Tables remain usable on mobile using cards/priority columns or controlled internal scrolling.
- [ ] Dropdown menus stay inside the viewport and expose the same actions as desktop.
- [ ] Search, sort and pagination controls remain usable on mobile.

## 3. Interaction and accessibility blockers

- [ ] Primary touch targets are at least 44×44 px where practical.
- [ ] Core workflows can be operated by mouse, touch and keyboard.
- [ ] `:focus-visible` state is clearly visible.
- [ ] Icon-only controls have accessible names.
- [ ] Dialog/dropdown semantics are exposed to assistive technology.
- [ ] Normal text contrast targets 4.5:1 or better.
- [ ] State is not communicated by color alone.
- [ ] `prefers-reduced-motion` is respected.
- [ ] Mutating controls show busy/disabled feedback and prevent accidental double submission.
- [ ] Loading, empty and error/retry states are understandable.

## 4. Internationalization blockers

- [ ] Persian RTL core flows are usable.
- [ ] English LTR core flows are usable.
- [ ] Long translated labels do not clip or make controls unreachable.
- [ ] Numbers/identifiers that need LTR presentation remain readable inside RTL pages.
- [ ] 100%, 125% and 150% browser zoom do not break core admin workflows.

## 5. Public repository privacy blockers

- [ ] No `.env`, DB, `.ovpn`, private key, certificate, token or credential is committed.
- [ ] No live Production IP/domain/customer/user/UUID is present in public docs or screenshots.
- [ ] Screenshots use sanitized/demo data only.
- [ ] Secret/private-material CI scan passes.
- [ ] Release artifact is generated from the sanitized release tree.
- [ ] Release artifact SHA256 is published.

## 6. Documentation blockers

- [ ] `AGENTS.md` task evidence is updated.
- [ ] `ROADMAP.md` matches the release scope.
- [ ] `CHANGELOG.md` contains the release-visible changes.
- [ ] English README/UI guide is updated for visible workflow changes.
- [ ] Persian README/UI guide has equivalent coverage.
- [ ] New/changed visible workflows have sanitized desktop/mobile screenshots.
- [ ] Documentation links and image paths resolve from `main`.

## 7. Release publication blockers

- [ ] `VERSION` matches the intended tag.
- [ ] Release notes list features, fixes, known issues, upgrade and rollback notes.
- [ ] CI on the release commit is green.
- [ ] Git tag points at the verified release commit.
- [ ] GitHub Release is published, not Draft/Prerelease unless explicitly intended.
- [ ] Source artifact and `.sha256` asset are uploaded and verified.
- [ ] Final Production health verification passes after deployment (or deployment is explicitly not part of the release).

## Active patch mandatory task IDs

The release is blocked until the applicable UI/quality tasks `PVN-100..139` in `AGENTS.md` are either `[x] DONE` with evidence or explicitly deferred/rejected with a documented reason that does not compromise core accessibility/availability.
