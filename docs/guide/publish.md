# Publishing

Follow the [Airlock release workflow](../../apps/airlock/README.md) for release preparation, automatic publication and registry setup.

## First npm publication

Use a clean, reviewed checkout of `main` with prepared versions and a passing quality gate. Publish any retained workspace dependencies first. Your npm account needs publishing rights for the package's scope and two-factor authentication enabled.

1. Replace `path/to/package` with the npm workspace directory, then log in and publish it interactively:

   ```sh
   npm login --registry=https://registry.npmjs.org
   pnpm --dir path/to/package publish --access public
   ```

   Complete the browser or one-time-password prompts. pnpm runs the package's packing hooks and applies its publication metadata. Confirm the exact version appears on npm. See [npm's public-package instructions](https://docs.npmjs.com/creating-and-publishing-scoped-public-packages/) and [pnpm publish](https://pnpm.io/cli/publish).

2. Open the package's **Settings → Trusted Publisher** on npmjs.com and select **GitHub Actions**. For this repository, configure:

   - Organization: `zyplux`.
   - Repository: `zyplux`.
   - Workflow filename: `release.yml`.
   - Environment: the target's `environment` in `airlock-targets.toml`, defaulting to `npm`.
   - Allowed actions: enable **Allow npm publish** for direct publication.

   Follow [npm's trusted-publisher instructions](https://docs.npmjs.com/trusted-publishers/). The workflow obtains its publishing credentials through OIDC.

3. Rerun the failed release job, or dispatch `release.yml` on `main` with the target's `<table-name>-v<version>` tag. Airlock reconciles the manually published version with its GitHub release. Subsequent prepared releases publish automatically after merge.
