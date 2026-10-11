# RKJO Education — B/T supervision demo

This is a visual prototype only. State exists in browser memory. Nothing is persisted, and there is no live teacher identity, learner information, API integration or network safety alert.

Acceptance:
1. Navigate to /education/supervision-demo.
2. Pause: status becomes paused; repeat pause is disabled.
3. Resume: status becomes active; repeat resume is disabled.
4. End: status becomes ended; resume is disabled.
5. Simulate an alert; it appears pending. Acknowledge; it becomes acknowledged.
6. No genuine user data or real session command is shown or sent.

Tests: npm --prefix apps/web run lint && npm --prefix apps/web run build && npm --prefix apps/web audit --omit=dev.

Next: replace simulated handlers with F-authorized backend endpoints and S->T durable events, with tenant isolation and teacher assignment tests.
