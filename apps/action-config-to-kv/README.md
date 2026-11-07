# Config to KV

Publishes a config repository's Worker snapshot to its environment's Cloudflare KV namespace. The repository supplies its pinned config-validator, including the snapshot CLI and required secret bindings.

Use after successful CI on main:

```yaml
- uses: zyplux/zyplux/apps/action-config-to-kv@config-to-kv-v1
  with:
    environment: staging
    cloudflare-account-id: ${{ vars.CLOUDFLARE_ACCOUNT_ID }}
    cloudflare-api-token: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

The action checks deployed Worker compatibility and secret bindings, updates the email maintenance schedule when needed, and publishes changed snapshots. First publication requires the KV namespace; Workers may be deployed afterwards.
