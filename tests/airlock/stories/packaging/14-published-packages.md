# 14. [Publishing installable npm packages](14-published-packages.test.ts)

## 14.1 packing release targets

### 14.1.1 passes Publint for every built npm archive

Every npm target in `release-targets.toml` is built and packed with pnpm. Each package's `prepack` script runs Publint over the publishable archive with pnpm's manifest transformations applied. Warnings and errors prevent packing.
