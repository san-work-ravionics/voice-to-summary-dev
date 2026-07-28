## Payments Vendor Integration — Meridian Pay

## Vendor Selection
Meridian Pay was selected over the incumbent processor for two reasons:
broader regional payout support and lower per-transaction fees at this
release's projected volume. This is a new vendor relationship — no prior
production history with them, which is why sandbox access on day one is a
hard requirement rather than a preference.

## Integration Approach
1. Sandbox environment provisioning (target: week 1).
2. SDK integration into the payments module.
3. Webhook-based reconciliation for payment status updates (avoids polling).
4. Staging certification against Meridian's test suite (target: week 4-6).
5. Production cutover only after QA sign-off on the full test suite,
   including failure-mode handling (declined payments, webhook retries,
   timeout handling).

## Security & Compliance
No card data touches application servers at any point — Meridian's hosted
fields handle card entry directly, which qualifies the integration for
**PCI DSS SAQ-A** (the lightest self-assessment tier) rather than a full PCI
audit. This must not change without a new compliance review.

## Risk Notes
Because this is a new vendor, the sandbox's fidelity to production behavior
is unproven going in — this is the single highest-risk workstream in the
release and should get priority engineering attention if any workstream
needs to be reprioritized.
