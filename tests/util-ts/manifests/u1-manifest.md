# u1. [Discovering and reading package manifests for dependencies and repository info](u1-manifest.test.ts)

## u1.1 parsing manifest text into typed shapes

### u1.1.1 parses package json text into a typed manifest and strips unknown keys

### u1.1.2 tolerates the array form of workspaces

### u1.1.3 parses pyproject toml text with pep 621 and pep 735 dependency sections and strips unknown keys

## u1.2 collecting and normalizing dependency names from a manifest

### u1.2.1 collects npm catalog and dependency field names while skipping workspace local specs

### u1.2.2 collects python requirement names across every section while dropping python itself

### u1.2.3 normalizes an underscored requirement name into its pep 503 canonical form
### u1.2.4 normalizes a dotted requirement name with a version specifier
### u1.2.5 returns undefined when no package name can be parsed from a requirement
## u1.3 resolving a manifest's repository url

1. reads the url from a string repository field
2. reads the url from an object repository field
3. returns undefined when no repository is declared

## u1.4 discovering manifests tracked by git

### u1.4.1 lists tracked manifests under the repo and excludes ignored paths

### u1.4.2 discovers manifests across nested repositories when the directory itself is outside any repository
