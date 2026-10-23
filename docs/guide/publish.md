# Publishing

The [release workflow](../../.changeset/README.md) prepares package versions and concise changelog entries in each releasable feature PR. On pushes to `main`, `release.yml` selects pending targets from `release-targets.toml` through the shared [Airlock action](../../apps/action-airlock/README.md), publishes npm targets together with native pnpm, and publishes other targets individually. GitHub releases contain the corresponding reviewed changelog entry. Completed artifacts and releases are preserved; retries complete missing publication steps.

`./just release` manually creates releases for pending versions from a clean, synchronized `main` checkout and watches their publication. The release workflow also supports manual retries on `main` and per-tag GitHub release events.

Established npm and PyPI packages use OIDC trusted publishing. New packages need the registry setup below.

| Registry | First publish of a new package                  | Token in CI            |
| -------- | ----------------------------------------------- | ---------------------- |
| npm      | run `bootstrap-npm` (token), enable its publisher | `NPM_TOKEN`, bootstrap only |
| PyPI     | add a pending publisher, then release           | none (OIDC)            |

## Add a new package

1. Add a `[[target]]` to `release-targets.toml`.
2. Do the one-time registry setup below (npm or PyPI).
3. Run `pnpm change` and prepare its versions and changelog. Python targets also need a private `package.json` beside `pyproject.toml` for pnpm discovery. Preparation synchronizes their versions through uv.
4. Review and merge the prepared release. The workflow publishes it through OIDC.

## GitHub Actions

Declare `kind = "action"`, `repository`, `tag_prefix` and `major_tag_prefix` in `release-targets.toml`, and add a workspace `package.json` for the action version. Include its entrypoint and implementation in `surface`. Preparation synchronizes a native Python version when the version source is `pyproject.toml`.

Merging the prepared release creates a fixed GitHub release such as `setup-pm-v1.0.0` with the reviewed changelog entry, then updates `setup-pm-v1` to the newest published stable release in that major. The floating tag has no GitHub release. Workflow retries also repair a missing or stale floating tag. GitHub Actions require `contents: write` for publication.

## Registry setup

### npm — bootstrap with a token, then switch to OIDC

npm has no pending publishers: the package must already exist before trusted publishing can be enabled, and that first publish needs a credential.

1. **Bootstrap** — Actions → **bootstrap-npm** → **Run workflow**, label e.g. `@zyplux/util`. This publishes the first version using the `NPM_TOKEN` secret.
2. **Enable trusted publishing** — npmjs.com → the package → **Settings → Trusted Publishing → GitHub Actions**:
   - Organization `zyplux` · Repository `zyplux` · Workflow `release.yml` · Environment *(blank)*
   - The `npm` job in `release.yml` runs with **no** `environment:`, so leave Environment blank — npm matches the OIDC environment claim exactly.
   - CLI alternative (requires interactive 2FA; `pnpx npm@11` runs a pinned npm version without a separate install):

     ```sh
     pnpx npm@11 login
     pnpx npm@11 trust github @zyplux/util --file release.yml --repo zyplux/zyplux --allow-publish
     ```

3. The release workflow publishes subsequent versions through OIDC with automatic provenance.

Trusted-publisher setup cannot be automated from CI — npm gates it behind interactive account 2FA and rejects automation tokens by design. Until step 2 is done, the package's releases fail (no token on the release path); finish it right after the bootstrap.

### PyPI — pending publisher, no bootstrap

PyPI authorizes the workflow *before* the package exists, so there is no token and no bootstrap step.

1. PyPI → **Account → Publishing → Add a pending publisher**:
   - PyPI Project Name `<dist-name>` (e.g. `zyplux-cerberus`) · Owner `zyplux` · Repository `zyplux` · Workflow `release.yml` · Environment `pypi`
   - The environment must match `environment: pypi` on the `pypi` job in `release.yml`.
2. Prepare and merge the release; the PyPI job publishes the first version through OIDC.

## Renew tokens

- **npm** — `NPM_TOKEN` is used only to bootstrap a brand-new package's first publish; established packages release via OIDC and need no token. To rotate it before a bootstrap (or when it expires): npm → **Access Tokens → Generate → Granular Access Token** (scope `@zyplux`, packages read + write, set an expiry) → update the `NPM_TOKEN` repository secret.
- **PyPI** — none. Trusted publishing uses no API tokens.
