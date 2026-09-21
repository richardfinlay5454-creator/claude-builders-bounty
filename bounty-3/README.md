# Destructive-command PreToolUse guard

This contribution implements bounty #3 with a shareable Claude Code `PreToolUse`
hook. It reads the tool-call JSON from stdin and denies only the destructive
patterns required by the bounty:

- recursive forced deletion (`rm -rf`, including equivalent combined flags)
- `DROP TABLE`
- `git push --force` / `--force-with-lease`
- `TRUNCATE`
- `DELETE FROM` statements that do not contain a `WHERE` clause

Every blocked attempt is appended to `~/.claude/hooks/blocked.log` with the UTC
timestamp, attempted command, project path, and reason. Safe commands emit no
decision, so Claude Code's normal permission flow continues unchanged.

## Install

From the repository root, copy the committed hook and settings into a project:

```bash
mkdir -p .claude/hooks && cp .claude/hooks/destructive_command_guard.py .claude/hooks/
cp .claude/settings.json .claude/settings.json
```

The repository already contains the hook at those paths, so when this contribution
is checked out directly there is nothing else to install.

## Verify

```bash
python -m unittest discover -s tests -p "test_*.py"
```

The tests exercise each required blocked pattern, safe near-misses, structured
denial output, and append-only audit logging without executing any destructive
command.
