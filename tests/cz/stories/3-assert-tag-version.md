# 3. [Asserting a release tag matches its target's version](3-assert-tag-version.test.ts)

## 3.1 asserting a tag against the release manifest

- logs a confirmation when the tag matches its target's declared version
- rejects a tag no release target owns
- rejects a tag whose version does not match the manifest
