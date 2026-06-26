# Publishing

Releases are cut by `just release` (`czyp release-bumped-targets`): it creates a GitHub
release per bumped target in `release-targets.toml`, and `release.yml` publishes it. A
`resolve` job reads the tag's registry kind from the manifest, then one per-registry job
runs `czyp publish-tagged-target "$TAG"`. Established packages publish via OIDC **trusted
publishing** (no
token) on both npm and PyPI. A brand-new package needs a one-time setup first, and
that setup differs by registry.

| Registry | First publish of a new package                  | Token in CI            |
| -------- | ----------------------------------------------- | ---------------------- |
| npm      | run `bootstrap-npm` (token), enable its publisher | `NPM_TOKEN`, bootstrap only |
| PyPI     | add a pending publisher, then release           | none (OIDC)            |

## Add a new package

1. Add a `[[target]]` to `release-targets.toml`.
2. Do the one-time registry setup below (npm or PyPI).
3. Bump the version — from then on `just release` publishes new versions tokenlessly
   via OIDC, for both npm and PyPI.

### npm — bootstrap with a token, then switch to OIDC

npm has no pending publishers: the package must already exist before trusted
publishing can be enabled, and that first publish needs a credential.

1. **Bootstrap** — Actions → **bootstrap-npm** → **Run workflow**, label e.g.
   `@zyplux/util`. This publishes the first version using the `NPM_TOKEN` secret.
2. **Enable trusted publishing** — npmjs.com → the package → **Settings → Trusted
   Publishing → GitHub Actions**:
   - Organization `zyplux` · Repository `zyp-cerberus` · Workflow `release.yml` ·
     Environment *(blank)*
   - The `npm` job in `release.yml` runs with **no** `environment:`, so leave
     Environment blank — npm matches the OIDC environment claim exactly.
   - CLI alternative (requires interactive 2FA; `bunx` avoids installing npm):

     ```sh
     bunx npm@latest login
     bunx npm@latest trust github @zyplux/util --file release.yml --repo zyplux/zyp-cerberus --allow-publish
     ```

3. From then on `just release` publishes new versions via OIDC — no token, with
   automatic provenance.

Trusted-publisher setup cannot be automated from CI — npm gates it behind interactive
account 2FA and rejects automation tokens by design. Until step 2 is done, the
package's releases fail (no token on the release path); finish it right after the
bootstrap.

### PyPI — pending publisher, no bootstrap

PyPI authorizes the workflow *before* the package exists, so there is no token and
no bootstrap step.

1. PyPI → **Account → Publishing → Add a pending publisher**:
   - PyPI Project Name `<dist-name>` (e.g. `zyplux-cerberus`) · Owner `zyplux` ·
     Repository `zyp-cerberus` · Workflow `release.yml` · Environment `pypi`
   - The environment must match `environment: pypi` on the `pypi` job in `release.yml`.
2. Bump and `just release` — the PyPI job publishes the first version via OIDC.

## Renew tokens

- **npm** — `NPM_TOKEN` is used only to bootstrap a brand-new package's first
  publish; established packages release via OIDC and need no token. To rotate it
  before a bootstrap (or when it expires): npm → **Access Tokens → Generate →
  Granular Access Token** (scope `@zyplux`, packages read + write, set an expiry) →
  update the `NPM_TOKEN` repository secret.
- **PyPI** — none. Trusted publishing uses no API tokens.
