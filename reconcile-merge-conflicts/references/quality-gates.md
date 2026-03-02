# Quality Gates

Run checks before each commit-producing continuation step and run full checks again after reconciliation.

## Command discovery and precedence

### JavaScript / TypeScript (`package.json`)

Determine package manager from lockfiles when possible:

- `pnpm-lock.yaml` → `pnpm run`
- `yarn.lock` → `yarn run`
- `package-lock.json` → `npm run`
- `bun.lockb` → `bun run`

Read scripts and run in this order when available:

1. `typecheck` (or `type-check`)
2. `lint`
3. `test` (or targeted test command for changed scope)
4. `build`
5. `format:check` (or formatter verification command)

If no scripts exist, report that gap explicitly.

### Python (`pyproject.toml`, `tox.ini`, `noxfile.py`)

Run configured project commands in this order when available:

1. format/lint checks
2. type checks
3. tests
4. build/package checks

### Rust (`Cargo.toml`)

Run when applicable:

1. `cargo fmt --check`
2. `cargo clippy`
3. `cargo test`
4. `cargo build`

### Go (`go.mod`)

Run when applicable:

1. `gofmt -l .` (expect no output)
2. `go vet ./...`
3. `go test ./...`
4. `go build ./...`

### Swift / Apple platforms (Xcode/SwiftPM)

Use configured project workflows for format/lint/type/test/build.

## Reporting rules

For each command, report:

- command run
- pass/fail result
- whether it was full or targeted

Never claim success for commands not run.
