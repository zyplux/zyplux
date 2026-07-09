import * as z from 'zod';

export const VersionSourceSchema = z.union([
  z.object({ file: z.string(), json: z.string() }),
  z.object({ file: z.string(), regex: z.string() }),
]);

export const TargetSchema = z.object({
  kind: z.enum(['ghcr', 'npm', 'pypi']),
  label: z.string(),
  surface: z.array(z.string()),
  tag_prefix: z.string(),
  version: VersionSourceSchema,
});

export const ManifestSchema = z.object({ target: z.array(TargetSchema) });

export const DepsCatalogSchema = z.array(z.string());

export type Manifest = z.infer<typeof ManifestSchema>;
export type Target = z.infer<typeof TargetSchema>;
export type VersionSource = z.infer<typeof VersionSourceSchema>;
