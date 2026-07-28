## Product Requirements Document — Mobile App Redesign

## Goals
Improve onboarding conversion and refresh the app's visual design, with a hard
launch target of 5 months from kickoff. Current onboarding completion rate is
60%; this release targets 85%+.

## Workstreams

### Onboarding Flow
Reduce the onboarding flow from 7 steps to 4. Notification-permission requests
must be preceded by a short in-app explainer screen rather than triggering the
OS prompt immediately, based on prior user research showing abrupt permission
prompts hurt completion.

### Payments Integration
New payments provider: **Meridian Pay**, selected for regional payout support
and lower per-transaction fees than the incumbent processor. Sandbox access
must be provisioned in week 1 so integration risk surfaces early. Target:
certification complete within 6 weeks of kickoff.

### Visual Refresh (Dark Mode)
Dark mode ships using the existing **Aurora Design System**'s token-based
theming — semantic color tokens, not per-screen manual overrides — so future
theme changes don't require touching individual screens.

### Legal / Privacy
Updated consent language for notification permissions requires legal
sign-off. Privacy review must confirm the release aligns with the company's
SOC 2 Type II commitments before launch.

### Analytics Instrumentation
Funnel events for the new onboarding flow are instrumented through the
internal **Compass Analytics** platform. Minimum required events: flow start,
each step completion, permission-prompt shown/accepted/declined, flow
complete.

### Localization
Out of scope for this release. Revisit for a future release; do not silently
drop the request — log it as a backlog item.

## Success Metrics
- Onboarding completion rate ≥ 85% (baseline: 60%).
- Payments integration live with zero Sev-1 incidents in first 30 days.
- Dark mode available on 100% of screens at launch.
