# RKJO Education — CE1 Classe interactive V2

## Scope

Adds an accessible pointer-enabled drawing slate (mouse, finger, stylus), undo/clear and coarse eraser; clickable physical-token transfer 8+5 -> 10+3; teacher "Je n'ai pas compris" rule-based reformulations.

Local demo only. No LLM, audio, uploads, persistence, student login, or model-based mastery assessment.

## Functional acceptance

1. /education/classe-ce1 displays 8 cyan and 5 yellow tokens initially.
2. Clicking "Déplacer un jeton" twice produces 10 cyan and 3 yellow tokens and a clear explanation.
3. Additional clicks cannot transfer more than two tokens.
4. "Je n'ai pas compris" produces a different guided explanation; during practice, it counts as assistance.
5. During practice, a wrong answer does not advance. A correct answer advances to a separate independent question 7 + 6.
6. During proof, the help/reformulation controls and transfer control are hidden and the decomposition is hidden.
7. The drawing slate clears upon entering proof; strokes can be drawn by mouse and touch, undone and cleared.
8. A failed autonomous answer yields a remediation recommendation, without granting mastery.
9. A successful independent answer yields a success statement explicitly scoped to this demo.
10. The editor and teacher demo do not call external AI APIs or persist any personal data.
11. Verify small screen, keyboard operation of buttons, Next.js compile and lint.

## Commands

```bash
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web audit --omit=dev
npm --prefix apps/web run dev -- --port 3003
```

Open http://localhost:3003/education/classe-ce1.

## Integration next

Backend contracts, JWT scopes, durable learner progress and formal mastery proof remain necessary before presenting this as a real AI tutor.
