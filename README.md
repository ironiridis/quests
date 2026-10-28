# Quests (Home Assistant custom integration)

`quests` is a custom Home Assistant integration that helps households track recurring tasks ("quests") that need completion and optional responses.

This repository is scaffolded for **HACS-first development** and intended to evolve toward Home Assistant core contribution quality over time.

## Current scaffold features

- Config-entry based setup (`Settings` → `Devices & Services` → `Add Integration`).
- **Realm-based** task grouping via config subentries:
  - open the Quests integration
  - click **Add Realm**
  - select enrolled Home Assistant users (eligible task owners)
  - define one or more repeating tasks in the guided flow
- Per-realm **NPC device** containing:
  - event outputs for each enrolled user (assigned, due, completed, checked, disabled)
  - realm-level summary states (total, due, overdue, requires response)
- Per-task devices (linked via NPC) containing:
  - disable switch (suppresses due/next + notifications while disabled)
  - complete button
  - check button (when check limit > 0)
  - champion selector control
  - champion state output (sticky owner display name)
  - due binary sensor
  - next-due timestamp sensor
- Local storage for repeating task state.
- Services to:
  - complete a realm task (with optional response text + actor)
  - check a realm task (defers 24h, respects check limit)
- Sensors for high-level status:
  - total quests
  - due quests
  - overdue quests
  - due quests requiring response

## Repository layout

- `custom_components/quests/` — Home Assistant integration source
- `hacs.json` — HACS metadata

## Installation (HACS)

1. In Home Assistant, open **HACS**.
2. Add this repository as a **Custom repository** of type **Integration**.
3. Install **Quests** from HACS.
4. Restart Home Assistant.
5. Add **Quests** from **Settings → Devices & Services**.

## Quick start: add a realm + tasks

1. Add the Quests integration.
2. Open Quests in Devices & Services.
3. Click **Add Realm**.
4. Enter realm name (for example, `household`).
5. Select one or more Home Assistant users to enroll in the realm.
6. Add one or more tasks in the interactive flow, setting repeat interval, response requirement, and check limit.

After setup, open the realm's **NPC** device for realm summary + per-user event outputs, and open each task device for champion/check/complete/due/next outputs.

## Service examples

Complete a quest:

```yaml
service: quests.complete_quest
data:
  realm_id: "household"
  task_id: "take_out_recycling"
  actor: "Alex"
  response: "Done before pickup"
```

Check a quest (defers by 24 hours):

```yaml
service: quests.check_quest
data:
  realm_id: "household"
  task_id: "take_out_recycling"
```

## Development notes

This is an initial scaffold meant for iterative refinement. Next likely steps:

- richer data model (history, scoring, streaks, escalation)
- per-user views and assignment logic
- options flow and richer realm/task editing UX
- tests and quality-scale hardening
