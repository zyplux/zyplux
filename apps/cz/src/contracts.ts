import {
  IdSchema,
  PyProjectSchema,
  RepositorySchema,
  StringRecordSchema,
  VersionKeySchema,
} from '@zyplux/util/contracts';
import * as z from 'zod';

export const DepsCatalogSchema = z.array(z.string());

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

export type DepsDevPackage = z.infer<typeof DepsDevPackageSchema>;

const SourceClassificationSchema = z.object({
  is_test: z.boolean(),
  kind: z.enum(['prod', 'infra', 'demo', 'test', 'docs']),
  needs_tests: z.boolean(),
  root: z.string(),
});
export const SourceSnapshotSchema = z.record(z.string(), SourceClassificationSchema);

const PythonWorkspaceSchema = z.object({
  tool: z
    .object({
      uv: z
        .object({
          workspace: z
            .object({ exclude: z.array(z.string()).default([]), members: z.array(z.string()).default([]) })
            .optional(),
        })
        .optional(),
    })
    .optional(),
});
export const PythonWorkspaceManifestSchema = PyProjectSchema.and(PythonWorkspaceSchema);

export type SourceSnapshot = z.infer<typeof SourceSnapshotSchema>;
