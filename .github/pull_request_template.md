## Summary of Changes

Describe the changes made and link the relevant issue.

Fixes #(issue)

### Subsystem
- [ ] Web Studio (`web/`)
- [ ] Terminal CLI (`src/`)
- [ ] Headless Export API (`src/api/`)
- [ ] Documentation (`docs/`)

### Verification Checklist
- [ ] Pytest passes: `pytest`
- [ ] Python linting passes: `ruff check src tests`
- [ ] Python types pass: `mypy src`
- [ ] Frontend build passes: `cd web && npm run build`
- [ ] No external runtime pip dependencies added (core package remains stdlib only)
- [ ] Responsive design verified on desktop and mobile viewports
- [ ] Zero secrets or sensitive data included
