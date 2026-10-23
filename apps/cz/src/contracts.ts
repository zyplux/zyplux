import { IdSchema, RepositorySchema, StringRecordSchema, VersionKeySchema } from '@zyplux/util/contracts';
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
