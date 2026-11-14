# 14. [Consuming the util package](14-package-consumer.test.ts)

## 14.1 consuming published packages

### 14.1.2 supports util imports with an optional TypeScript peer

The packed util package's JSON API works without TypeScript installed. Compiler helpers work with the optional TypeScript peer. The temporary consumer reuses locally installed runtime dependencies.
