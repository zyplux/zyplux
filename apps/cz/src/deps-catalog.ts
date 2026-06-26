import type { ZodType } from 'zod';

import { mapWithConcurrency, normalizeRepoUrl } from '@zyplux/util';
import {
  findManifests,
  IdSchema,
  normalizePythonName,
  npmDependencyNames,
  PackageJsonSchema,
  PyProjectSchema,
  pythonRequirementNames,
  RepositorySchema,
  repositoryUrl,
  StringRecordSchema,
  VersionKeySchema,
} from '@zyplux/util/manifest';
import * as z from 'zod';

export type CollectDepReposOptions = {
  dir?: string;
  fetch?: FetchLike;
  localRepos?: Iterable<string>;
};

export type DependencyNames = { npm: string[]; pypi: string[] };

export type DepReposReport = { repos: string[]; unresolved: PackageRef[] };

export type PackageRef = { name: string; system: PackageSystem };

export type PackageSystem = 'npm' | 'pypi';

type FetchLike = (input: string | URL, init?: RequestInit) => Promise<Response>;

const VersionEntrySchema = z.object({ isDefault: z.boolean().optional(), versionKey: VersionKeySchema });
const DepsDevPackageSchema = z.object({ versions: z.array(VersionEntrySchema) });

const LinkSchema = z.object({ label: z.string(), url: z.string() });
const RelatedProjectSchema = z.object({ projectKey: IdSchema, relationType: z.string() });
const DepsDevVersionSchema = z.object({
  links: z.array(LinkSchema).optional(),
  relatedProjects: z.array(RelatedProjectSchema).optional(),
});

const NpmRegistrySchema = z.object({ homepage: z.string().optional(), repository: RepositorySchema.optional() });

const PypiInfoSchema = z.object({ home_page: z.string().nullish(), project_urls: StringRecordSchema.nullish() });
const PypiProjectSchema = z.object({ info: PypiInfoSchema });

const DEPS_DEV_SYSTEM: Record<PackageSystem, string> = { npm: 'npm', pypi: 'pypi' };
const RESOLVE_CONCURRENCY = 8;

const byLocale = (left: string, right: string) => left.localeCompare(right);

const scanWorkspace = async (dir: string) => {
  const npm = new Set<string>();
  const pypi = new Set<string>();
  const localNpmNames = new Set<string>();
  const localPyNames = new Set<string>();
  const localRepos = new Set<string>();

  const manifests = await findManifests(dir);
  for (const file of manifests) {
    const text = await Bun.file(file).text();
    if (file.endsWith('package.json')) {
      const parsed = PackageJsonSchema.safeParse(JSON.parse(text));
      if (!parsed.success) continue;
      const data = parsed.data;
      if (data.name !== undefined) localNpmNames.add(data.name);
      const repo = normalizeRepoUrl(repositoryUrl(data.repository));
      if (repo !== undefined) localRepos.add(repo);
      for (const name of npmDependencyNames(data)) npm.add(name);
    } else {
      const parsed = PyProjectSchema.safeParse(Bun.TOML.parse(text));
      if (!parsed.success) continue;
      const data = parsed.data;
      const ownName = data.project?.name;
      if (ownName !== undefined) localPyNames.add(normalizePythonName(ownName) ?? ownName);
      const projectUrls = Object.values(data.project?.urls ?? {});
      for (const url of projectUrls) {
        const repo = normalizeRepoUrl(url);
        if (repo !== undefined) localRepos.add(repo);
      }
      for (const name of pythonRequirementNames(data)) pypi.add(name);
    }
  }

  return {
    localRepos,
    npm: [...npm].filter(name => !localNpmNames.has(name)).toSorted(byLocale),
    pypi: [...pypi].filter(name => !localPyNames.has(name)).toSorted(byLocale),
  };
};

export const collectDependencyNames = async (dir: string): Promise<DependencyNames> => {
  const { npm, pypi } = await scanWorkspace(dir);
  return { npm, pypi };
};

const fetchJson = async <T>(fetchImpl: FetchLike, url: string, schema: ZodType<T>): Promise<T | undefined> => {
  try {
    const response = await fetchImpl(url);
    if (!response.ok) return undefined;
    const parsed = schema.safeParse(await response.json());
    return parsed.success ? parsed.data : undefined;
  } catch {
    return undefined;
  }
};

const defaultVersion = (pkg: undefined | z.infer<typeof DepsDevPackageSchema>) =>
  pkg?.versions.find(entry => entry.isDefault === true)?.versionKey.version ?? pkg?.versions.at(-1)?.versionKey.version;

const resolveViaDepsDev = async (system: PackageSystem, name: string, fetchImpl: FetchLike) => {
  const base = `https://api.deps.dev/v3/systems/${DEPS_DEV_SYSTEM[system]}/packages/${encodeURIComponent(name)}`;
  const version = defaultVersion(await fetchJson(fetchImpl, base, DepsDevPackageSchema));
  if (version === undefined) return;
  const detail = await fetchJson(fetchImpl, `${base}/versions/${encodeURIComponent(version)}`, DepsDevVersionSchema);
  const fromProjects = detail?.relatedProjects?.find(project => project.relationType === 'SOURCE_REPO')?.projectKey.id;
  const fromLinks = detail?.links?.find(link => link.label === 'SOURCE_REPO')?.url;
  return normalizeRepoUrl(fromProjects ?? fromLinks);
};

const resolveViaRegistry = async (system: PackageSystem, name: string, fetchImpl: FetchLike) => {
  if (system === 'npm') {
    const url = `https://registry.npmjs.org/${name.replace('/', '%2F')}/latest`;
    const pkg = await fetchJson(fetchImpl, url, NpmRegistrySchema);
    return normalizeRepoUrl(repositoryUrl(pkg?.repository)) ?? normalizeRepoUrl(pkg?.homepage);
  }
  const pkg = await fetchJson(fetchImpl, `https://pypi.org/pypi/${encodeURIComponent(name)}/json`, PypiProjectSchema);
  const urls = Object.entries(pkg?.info.project_urls ?? {});
  const labelled = urls.find(([label]) => /code|github|repository|source/i.test(label))?.[1];
  return normalizeRepoUrl(labelled) ?? normalizeRepoUrl(pkg?.info.home_page ?? undefined);
};

export const resolveSourceRepo = async (
  system: PackageSystem,
  name: string,
  fetchImpl: FetchLike = globalThis.fetch,
): Promise<string | undefined> => {
  const viaDepsDev = await resolveViaDepsDev(system, name, fetchImpl);
  if (viaDepsDev !== undefined) return viaDepsDev;
  return resolveViaRegistry(system, name, fetchImpl);
};

export const collectDepRepos = async (options: CollectDepReposOptions = {}): Promise<DepReposReport> => {
  const { dir = process.cwd(), fetch: fetchImpl = globalThis.fetch, localRepos } = options;
  const scan = await scanWorkspace(dir);
  const excluded = new Set(scan.localRepos);
  const extraRepos = localRepos ?? [];
  for (const repo of extraRepos) {
    const normalized = normalizeRepoUrl(repo);
    if (normalized !== undefined) excluded.add(normalized);
  }

  const refs: PackageRef[] = [
    ...scan.npm.map(name => ({ name, system: 'npm' as const })),
    ...scan.pypi.map(name => ({ name, system: 'pypi' as const })),
  ];
  const resolved = await mapWithConcurrency(refs, RESOLVE_CONCURRENCY, async ref => ({
    ref,
    repo: await resolveSourceRepo(ref.system, ref.name, fetchImpl),
  }));

  const repos = new Set<string>();
  const unresolved: PackageRef[] = [];
  for (const { ref, repo } of resolved) {
    if (repo === undefined) {
      unresolved.push(ref);
    } else if (!excluded.has(repo)) {
      repos.add(repo);
    }
  }

  return {
    repos: [...repos].toSorted(byLocale),
    unresolved: unresolved.toSorted((a, b) => a.system.localeCompare(b.system) || a.name.localeCompare(b.name)),
  };
};
