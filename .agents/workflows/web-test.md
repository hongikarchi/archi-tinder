---
description: Run a visual web test using the Antigravity browser subagent to cross-validate the UI
---

1. Use the `browser_subagent` tool to perform a visual QA test on the local frontend application.
2. By default, check `http://localhost:5174` (or the URL the user specifies).
3. Instruct the `browser_subagent` to:
   - Navigate to the local server URL.
   - Look for any visible layout breakage, missing text, or obvious UI errors.
   - Capture a screenshot of the main screen and return.
4. Once the subagent finishes, review the results (the screenshots) and provide a concise QA report to the user, highlighting any visual issues.