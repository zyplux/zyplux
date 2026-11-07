# Config to KV

Publishes a config repository's Worker snapshot to its environment's Cloudflare KV namespace. The repository supplies its pinned config-validator, including the snapshot CLI and required secret bindings.

Use after successful CI on main with job permissions `contents: read`, `packages: read` and `id-token: write`:

```yaml
- uses: zyplux/zyplux/apps/action-config-to-kv@config-to-kv-v1
  with:
    environment: staging
    cloudflare-account-id: ${{ vars.CLOUDFLARE_ACCOUNT_ID }}
    cloudflare-api-token: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

The action checks deployed Worker compatibility and secret bindings, publishes changed snapshots and calls endpoints declared by the Workers' `BOOTSTRAP_URL` binding. Calls use GitHub Actions OIDC with the endpoint URL as audience and carry the published config revision. HTTP 409 is retried for up to two minutes while KV propagates; other failures fail the job. First publication requires the KV namespace; Workers may be deployed afterwards.

Code deployment workflows use `zyplux/zyplux/apps/action-config-to-kv/bootstrap@config-to-kv-v1` with the same inputs and `id-token: write`. This entry point notifies deployed Workers using the published KV revision.
