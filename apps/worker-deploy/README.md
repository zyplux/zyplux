# Worker Deploy

Synchronous Cloudflare Worker deployment through the caller's pinned Wrangler. Python 3.14+; install `zyplux-worker-deploy==0.1.0` in the caller's uv workspace and invoke `uv run --locked worker-deploy`. Pin Wrangler in that project's package manifest and lockfile. The tool neither installs nor upgrades Wrangler.

Build a project using its own build command first, then deploy from that project's directory:

```sh
pnpm --filter @zyplux/web run build
uv run --locked worker-deploy --cwd apps/web --name zyplux-web --source-commit "$SOURCE_COMMIT" > receipt.json
```

With no `--config`, Wrangler discovers its configuration, including Vite's generated deployment configuration. Select Vite's `CLOUDFLARE_ENV` when building; use `--env` only for ordinary Wrangler environments. `--name` is the exact deployed name, including any environment suffix.

Deploy an immutable published bundle without bundling:

```sh
uv run --locked worker-deploy --cwd "$BUNDLE_DIR" --name identity-production --source-commit "$RELEASE_COMMIT" --bundle index.js --config deploy.json --strict --secrets-file "$PROTECTED_BINDINGS" --tag release-v1 > receipt.json
```

`--bundle` requires explicit config and passes `--no-bundle`. Omit `--domain` for private Workers. Repeated `--domain` and `--var KEY:VALUE`, plus `--tag`, `--strict`, `--config` and `--env`, map to Wrangler deploy flags. Variables are public; secret bindings belong in an owner-only JSON file containing string values (`chmod 600`). `--secrets-file` is resolved from the invoking directory. `--wrangler 'pnpm --filter @example/worker exec wrangler'` selects a caller-owned executable command without a shell. Other paths follow Wrangler's working-directory conventions.

Real deployments require `CLOUDFLARE_ACCOUNT_ID` and `CLOUDFLARE_API_TOKEN`. Both account-owned and user-owned tokens work: authentication checks the selected account's Worker scripts API, rather than a user-token endpoint. Give the token Workers Scripts access and permissions needed by the configured bindings/routes. Keep `account_id` out of Wrangler configuration, or match the selected account: Wrangler gives config precedence. After upload the tool verifies the exact version exists in the selected account. A failed post-upload check does not roll back an upload.

For credential-free compilation and packaging checks, append `--dry-run`. The tool omits secret bindings and removes Cloudflare credential variables from the child environment; it does not call the account API or emit a deployed version. Dry runs are not credential validation or a sandbox: caller-owned config and build hooks remain executable code. Run PR validation without production credentials.

Successful real deployments print one JSON object on stdout:

```json
{"status":"deployed","worker_name":"identity-production","version_id":"11111111-1111-4111-8111-111111111111","source_commit":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
```

The caller must supply the full source commit of the artifact; it can differ from the workflow checkout. Dry-run receipts use `status: "dry_run"` and omit `version_id`. Wrangler failure exits with its status; validation failures exit 1. Missing, ambiguous or mismatched upload receipts fail. Wrangler stdout/stderr and temporary debug/NDJSON files are withheld and removed to protect bindings; failures report the stage and exit status without dumping provider responses.

Callers own build selection, health checks, ordering, application compatibility, activation, email subscriptions and rollback. A receipt establishes the uploaded version, not application health. Python callers can use `subprocess.run(..., check=True, capture_output=True, text=True)` and parse stdout as JSON.

Wrangler's [deploy command](https://developers.cloudflare.com/workers/wrangler/commands/) and [machine-readable output](https://github.com/cloudflare/workers-sdk/blob/main/packages/wrangler/src/output.ts) define the upstream interface. Account checks use Cloudflare's [Worker scripts](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/methods/list/) and [Worker versions](https://developers.cloudflare.com/api/resources/workers/subresources/scripts/subresources/versions/methods/get/) APIs.
