import * as z from 'zod';

export const LooseRecordSchema = z.record(z.string(), z.unknown());
export const StringRecordSchema = z.record(z.string(), z.string());
export const StringArraySchema = z.array(z.string());
export const UnknownArraySchema = z.array(z.unknown());
export const UnknownArrayRecordSchema = z.record(z.string(), UnknownArraySchema);

export const IdSchema = z.object({ id: z.string() });
export const PackageVersionSchema = z.object({ version: z.string() });
export const VersionKeySchema = z.object({ version: z.string() });

export const GhSchema = {
  pr: z.object({
    isDraft: z.boolean(),
    mergeStateStatus: z.string(),
    number: z.int(),
    state: z.string(),
    url: z.string(),
  }),
  release: z.object({ tagName: z.string() }),
  releaseLookup: z.object({
    data: z.object({ repository: z.object({ release: IdSchema.nullable() }) }),
  }),
  repo: z.object({ nameWithOwner: z.string() }),
  reviews: z.array(z.object({ commit_id: z.string(), user: z.object({ login: z.string() }).nullable() })),
  run: z.object({
    conclusion: z.string(),
    databaseId: z.int(),
    headBranch: z.string(),
    status: z.string(),
  }),
};

export type GhPr = z.infer<typeof GhSchema.pr>;
export type GhRelease = z.infer<typeof GhSchema.release>;
export type GhRepo = z.infer<typeof GhSchema.repo>;
export type GhRun = z.infer<typeof GhSchema.run>;

const CatalogsSchema = z.record(z.string(), LooseRecordSchema);

const RepositoryObjectSchema = z.object({ url: z.string().optional() });
export const RepositorySchema = z.union([z.string(), RepositoryObjectSchema]);

const WorkspacesObjectSchema = z.object({
  catalog: LooseRecordSchema.optional(),
  catalogs: CatalogsSchema.optional(),
});
const WorkspacesSchema = z.union([StringArraySchema, WorkspacesObjectSchema]);

export const PackageJsonSchema = z.object({
  catalog: LooseRecordSchema.optional(),
  catalogs: CatalogsSchema.optional(),
  dependencies: LooseRecordSchema.optional(),
  devDependencies: LooseRecordSchema.optional(),
  name: z.string().optional(),
  optionalDependencies: LooseRecordSchema.optional(),
  peerDependencies: LooseRecordSchema.optional(),
  peerDependenciesMeta: z.record(z.string(), z.object({ optional: z.boolean().optional() })).optional(),
  repository: RepositorySchema.optional(),
  workspaces: WorkspacesSchema.optional(),
});

const ProjectSchema = z.object({
  dependencies: UnknownArraySchema.optional(),
  name: z.string().optional(),
  'optional-dependencies': UnknownArrayRecordSchema.optional(),
  urls: StringRecordSchema.optional(),
});

const UvSchema = z.object({ 'dev-dependencies': UnknownArraySchema.optional() });
const ToolSchema = z.object({ uv: UvSchema.optional() });

export const PyProjectSchema = z.object({
  'dependency-groups': UnknownArrayRecordSchema.optional(),
  project: ProjectSchema.optional(),
  tool: ToolSchema.optional(),
});

export type PackageJson = z.infer<typeof PackageJsonSchema>;
export type PyProject = z.infer<typeof PyProjectSchema>;

export const ArchitecturePackageSchema = z.looseObject({
  exports: z.unknown().optional(),
  name: z.string(),
});
export const WorkspaceConfigSchema = z.object({ packages: z.array(z.string()).default([]) });
