# Autonomous Execution Guidelines

## Autonomous Action Policy
- **Proactive Execution**: Always execute terminal commands, file creations, edits, tests, and repairs directly without asking for user permission or confirmation first.
- **Do Not Prompt For Approval**: When an error or task is identified, do not ask "Would you like me to proceed?" or "Should I run this?". Execute the necessary tools, commands, and edits autonomously.
- **Automated Verification**: Immediately run tests, linters, and type checkers after making code changes to verify correctness without waiting for a prompt.
- **Self-Directed Problem Solving**: When encountering an issue in CI, tests, or code, trace the root cause, apply the fix, and re-verify end-to-end.
