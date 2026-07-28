## Design Spec — Visual Refresh & Onboarding

## Dark Mode
Implemented via the Aurora Design System's semantic color tokens (e.g.
`surface.primary`, `text.onSurface`) rather than hardcoded per-screen colors,
so a single token-file change propagates everywhere. All screens must meet
WCAG 2.1 AA contrast ratios in both light and dark themes before sign-off —
this is a launch blocker, not a nice-to-have.

## Onboarding Flow Redesign
Old flow: 7 sequential screens, notification permission requested
immediately on screen 3. New flow: 4 screens, using progressive disclosure —
value proposition, minimal signup, a short explainer screen ("why we need
this") immediately before any OS permission prompt, then a single
confirmation screen. Every OS-level permission prompt in the new flow must be
preceded by an in-app explainer; this applies to notifications and any future
permission types added to the flow.

## Component Inventory
Screens affected: Welcome, Sign Up, Permission Explainer, Confirmation. All
four must ship with dark-mode variants at launch — partial dark-mode coverage
is not acceptable per the PRD's "100% of screens" success metric.
