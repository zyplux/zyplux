# u14. [Consuming the util package](u14-package-consumer.test.ts)

## u14.1 consuming published packages

### u14.1.2 supports util imports with an optional TypeScript peer

The packed util package's JSON API works without TypeScript installed. Compiler helpers work with the optional TypeScript peer. The temporary consumer reuses locally installed runtime dependencies.
