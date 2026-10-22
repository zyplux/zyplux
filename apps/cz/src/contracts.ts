import { IdSchema, RepositorySchema, StringRecordSchema, VersionKeySchema } from '@zyplux/util/contracts';
import * as z from 'zod';

export const VersionSourceSchema = z.union([
  z.object({ file: z.string(), json: z.string() }),
  z.object({ file: z.string(), regex: z.string() }),
]);

const TargetBaseSchema = z.object({
  label: z.string(),
  surface: z.array(z.string()),
  tag_prefix: z.string(),
  version: VersionSourceSchema,
});

export const TargetSchema = z.discriminatedUnion('kind', [
  TargetBaseSchema.extend({ kind: z.enum(['ghcr', 'npm', 'pypi']) }),
  TargetBaseSchema.extend({
    kind: z.literal('action'),
    major_tag_prefix: z.string().min(1),
    repository: z.string().regex(/^[\w.-]+\/[\w.-]+$/u),
  }),
]);

export const ActionReleasesSchema = z.array(
  z.array(z.object({ draft: z.boolean(), prerelease: z.boolean(), tag_name: z.string() })),
);

export const ManifestSchema = z.object({ target: z.array(TargetSchema) });

export const DepsCatalogSchema = z.array(z.string());

export const VersionFileSchema = z.record(z.string(), z.unknown());
export const VersionFieldSchema = z.string();

export const PythonReleaseSchema = z.object({ name: z.string(), private: z.literal(true), version: z.string() });

export const NpmPackageSchema = z.object({
  publishConfig: z.record(z.string(), z.unknown()).default({}),
});

export const NpmVersionsSchema = z.object({ versions: z.record(z.string(), z.unknown()) });

export const RegistryUrlSchema = z
  .url()
  .transform(registry => registry.replace(/\/$/u, ''))
  .pipe(z.enum(['https://registry.npmjs.org', 'https://npm.pkg.github.com']))
  .default('https://registry.npmjs.org');

export const GhcrTokenSchema = z.object({ token: z.string() });

const VersionEntrySchema = z.object({ isDefault: z.boolean().optional(), versionKey: VersionKeySchema });
export const DepsDevPackageSchema = z.object({ versions: z.array(VersionEntrySchema) });

const LinkSchema = z.object({ label: z.string(), url: z.string() });
const RelatedProjectSchema = z.object({ projectKey: IdSchema, relationType: z.string() });
export const DepsDevVersionSchema = z.object({
  links: z.array(LinkSchema).optional(),
  relatedProjects: z.array(RelatedProjectSchema).optional(),
});

export const NpmRegistrySchema = z.object({ homepage: z.string().optional(), repository: RepositorySchema.optional() });

const PypiInfoSchema = z.object({ home_page: z.string().nullish(), project_urls: StringRecordSchema.nullish() });
export const PypiProjectSchema = z.object({ info: PypiInfoSchema });

export type ActionTarget = Extract<Target, { kind: 'action' }>;
export type DepsDevPackage = z.infer<typeof DepsDevPackageSchema>;
export type Manifest = z.infer<typeof ManifestSchema>;
export type Target = z.infer<typeof TargetSchema>;
export type VersionSource = z.infer<typeof VersionSourceSchema>;
