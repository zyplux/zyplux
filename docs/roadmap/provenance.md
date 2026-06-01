# Roadmap: npm provenance

The current release workflow uses the all-Bun path (`bun publish`), which has no
provenance support. To add [provenance](https://docs.npmjs.com/generating-provenance-statements)
— a signed, publicly verifiable attestation linking each published tarball to the
source commit and the workflow that built it — switch the publish step to the npm
CLI. Bun stays responsible for packing, because npm does not understand the
`catalog:` protocol; `bun pm pack` resolves `catalog:`/`workspace:` into real
version ranges, and npm publishes that finished tarball.

## Changes to `.github/workflows/release.yml`

Grant the job an OIDC identity:

```yaml
permissions:
  contents: read
  id-token: write
```

Replace the `Authenticate to npm` and `Publish` steps with:

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: 22
    registry-url: https://registry.npmjs.org
- name: Pack with Bun, publish with provenance
  working-directory: packages/eslint-config
  run: |
    bun pm pack --destination .
    npm publish ./*.tgz --provenance --access public
  env:
    NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
```

The same `NPM_TOKEN` secret is reused. `setup-node` writes the `.npmrc` that wires
`NODE_AUTH_TOKEN` to the registry. Provenance requires `repository.url` in
`packages/eslint-config/package.json` to match this repo — already satisfied.

## Further step: tokenless publishing

Once a first version is published, register a Trusted Publisher for the package on
npmjs.com (repo `realSergiy/totvibe-eslint`, workflow `release.yml`). npm then
mints a short-lived token from the job's OIDC identity, so the `NPM_TOKEN` secret
can be deleted entirely. Provenance is emitted automatically; the `--provenance`
flag becomes redundant.
