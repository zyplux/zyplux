import * as z from 'zod';

export const VersionSourceSchema = z.union([
  z.object({ file: z.string(), json: z.string() }),
  z.object({ file: z.string(), regex: z.string() }),
]);

const TargetBaseSchema = z.object({
  environment: z.string().min(1).optional(),
  label: z.string().optional(),
  surface: z.array(z.string()),
  version: VersionSourceSchema,
});

export const TargetSchema = z.discriminatedUnion('kind', [
  TargetBaseSchema.extend({ kind: z.enum(['npm', 'pypi']) }),
  TargetBaseSchema.extend({
    artifact_command: z
      .tuple([z.string().min(1)])
      .rest(z.string())
      .optional(),
    assets: z.array(z.string().min(1)).default([]),
    kind: z.literal('ghcr'),
  }),
  TargetBaseSchema.extend({
    kind: z.literal('action'),
    repository: z.string().regex(/^[\w.-]+\/[\w.-]+$/u),
  }),
]);

export const ReleaseBatchSchema = z.object({
  environment: z.string().min(1),
  id: z.string().min(1),
  kind: z.enum(['npm', 'pypi', 'ghcr', 'action']),
  runner: z.literal('ubuntu-latest'),
  tags: z.array(z.string()).min(1),
});

export const ReleasePlanSchema = z.object({ include: z.array(ReleaseBatchSchema) });

export const ActionReleasesSchema = z.array(
  z.array(z.object({ draft: z.boolean(), prerelease: z.boolean(), tag_name: z.string() })),
);

export const ManifestSchema = z
  .object({ scope: z.string().min(1) })
  .catchall(TargetSchema)
  .transform(({ scope, ...targets }) => ({
    target: Object.entries(targets).map(([name, target]) => ({
      ...target,
      label: target.label ?? `${scope}/${name}`,
      tag_prefix: `${name}-v`,
    })),
  }));
export const VersionFileSchema = z.record(z.string(), z.unknown());
export const VersionFieldSchema = z.string();
export const PythonReleaseSchema = z.object({ name: z.string(), private: z.literal(true), version: z.string() });
export const NpmPackageSchema = z.object({ publishConfig: z.record(z.string(), z.unknown()).default({}) });
export const NpmVersionsSchema = z.object({ versions: z.record(z.string(), z.unknown()) });
export const PypiFilesSchema = z.object({ urls: z.array(z.object({ packagetype: z.string() })) });
export const RegistryUrlSchema = z
  .url()
  .transform(registry => registry.replace(/\/$/u, ''))
  .pipe(z.enum(['https://registry.npmjs.org', 'https://npm.pkg.github.com']))
  .default('https://registry.npmjs.org');
export const GhcrTokenSchema = z.object({ token: z.string() });

export type ActionTarget = Extract<Target, { kind: 'action' }>;
export type ReleaseBatch = z.infer<typeof ReleaseBatchSchema>;
export type Target = z.infer<typeof ManifestSchema>['target'][number];
export type VersionSource = z.infer<typeof VersionSourceSchema>;
