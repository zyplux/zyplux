# 19. [Flagging a type nothing else in the package uses](19-no-package-wide-unused-types.test.ts)

Each case is a small package built fresh in a temp directory (`lintPackage`, kept out of the repo's own
knip-scanned tree since the samples deliberately contain dead exports) from a `Record<filename, code>` map, paired
with an `outcome` map of the same shape recording the expected messageId (or `null` for no report) per file.

The rule doesn't care whether the type is exported: the message differs instead — an unused exported type suggests
moving it to (or colocating it with) whatever actually consumes it, an unused non-exported type is just dead code to
delete.

## 19.1 flagging a type nothing else in the package uses

A type only re-exported through one barrel hop is flagged, and so is one behind a chain of re-export hops — every
hop is a re-binding, not a use, so `getAliasedSymbol` resolves the whole chain back to the same declaration
regardless of depth. A declared-but-never-exported type is flagged too, with the non-exported message.

## 19.2 allowing a type used anywhere in the package

A type referenced in a real type position by a consumer file is not flagged. A type referenced only inside
another type's own definition (`Outer = { inner: Inner }`) is not flagged either — using `Inner` there counts as a
real use regardless of whether `Outer` itself ends up flagged as unused.

Enabled repo-wide via `zypluxRules` (`**/*.{ts,tsx}`), same as most other custom rules — see the rule's own
`docs.description` for the caveat about legitimate public-API types in a contracts/domain package, which this rule
will flag; scope it with `ignores` where that is the intent.
