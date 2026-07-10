import * as z from 'zod';

export const LooseRecordSchema = z.record(z.string(), z.unknown());
export const StringRecordSchema = z.record(z.string(), z.string());
export const StringArraySchema = z.array(z.string());
export const UnknownArraySchema = z.array(z.unknown());
export const UnknownArrayRecordSchema = z.record(z.string(), UnknownArraySchema);

export const IdSchema = z.object({ id: z.string() });
export const VersionKeySchema = z.object({ version: z.string() });

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
