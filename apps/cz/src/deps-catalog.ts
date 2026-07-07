import {
  fetchJson,
  findManifests,
  IdSchema,
  mapWithConcurrency,
  normalizePythonName,
  normalizeRepoUrl,
  npmDependencyNames,
  PackageJsonSchema,
  PyProjectSchema,
  pythonRequirementNames,
  RepositorySchema,
  repositoryUrl,
  StringRecordSchema,
  tryParseJson,
  tryParseToml,
  VersionKeySchema,
} from '@zyplux/util';
import * as z from 'zod';

type DepReposReport = { repos: string[]; unresolved: PackageRef[] };

type PackageRef = { name: string; system: PackageSystem };

type PackageSystem = 'npm' | 'pypi';

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

const RESOLVE_CONCURRENCY = 8;

const byLocale = (left: string, right: string) => left.localeCompare(right);

const readManifestFacts = async (file: string) => {
  const text = await Bun.file(file).text();
  if (file.endsWith('package.json')) {
    const manifest = tryParseJson(text, PackageJsonSchema);
    if (manifest === undefined) return;
    return {
      deps: npmDependencyNames(manifest),
      name: manifest.name,
      repos: [repositoryUrl(manifest.repository)].filter(url => url !== undefined),
      system: 'npm',
    };
  }
  const manifest = tryParseToml(text, PyProjectSchema);
  if (manifest === undefined) return;
  const name = manifest.project?.name;
  return {
    deps: pythonRequirementNames(manifest),
    name: name === undefined ? undefined : (normalizePythonName(name) ?? name),
    repos: Object.values(manifest.project?.urls ?? {}),
    system: 'pypi',
  };
};

const collectDepsNames = async (dir: string) => {
  const files = await findManifests(dir);
  const parsed = await Promise.all(files.map(file => readManifestFacts(file)));
  const facts = parsed.filter(fact => fact !== undefined);

  const externalNames = (system: PackageSystem) => {
    const local = facts.filter(fact => fact.system === system);
    const own = new Set(local.map(fact => fact.name));
    return [...new Set(local.flatMap(fact => fact.deps))].filter(name => !own.has(name)).toSorted(byLocale);
  };

  const declaredRepos = facts.flatMap(fact => fact.repos).map(url => normalizeRepoUrl(url));
  const localRepos = new Set(declaredRepos.filter(repo => repo !== undefined));
  return { localRepos, npm: externalNames('npm'), pypi: externalNames('pypi') };
};

const defaultVersion = (pkg: undefined | z.infer<typeof DepsDevPackageSchema>) =>
  pkg?.versions.find(entry => entry.isDefault === true)?.versionKey.version ?? pkg?.versions.at(-1)?.versionKey.version;

const resolveViaDepsDev = async (system: PackageSystem, name: string) => {
  const base = `https://api.deps.dev/v3/systems/${system}/packages/${encodeURIComponent(name)}`;
  const version = defaultVersion(await fetchJson(base, DepsDevPackageSchema));
  if (version === undefined) return;
  const detail = await fetchJson(`${base}/versions/${encodeURIComponent(version)}`, DepsDevVersionSchema);
  const fromProjects = detail?.relatedProjects?.find(project => project.relationType === 'SOURCE_REPO')?.projectKey.id;
  const fromLinks = detail?.links?.find(link => link.label === 'SOURCE_REPO')?.url;
  return normalizeRepoUrl(fromProjects ?? fromLinks);
};

const resolveViaRegistry = async (system: PackageSystem, name: string) => {
  if (system === 'npm') {
    const url = `https://registry.npmjs.org/${name.replace('/', '%2F')}/latest`;
    const pkg = await fetchJson(url, NpmRegistrySchema);
    return normalizeRepoUrl(repositoryUrl(pkg?.repository)) ?? normalizeRepoUrl(pkg?.homepage);
  }
  const pkg = await fetchJson(`https://pypi.org/pypi/${encodeURIComponent(name)}/json`, PypiProjectSchema);
  const urls = Object.entries(pkg?.info.project_urls ?? {});
  const labelled = urls.find(([label]) => /code|github|repository|source/i.test(label))?.[1];
  return normalizeRepoUrl(labelled) ?? normalizeRepoUrl(pkg?.info.home_page ?? undefined);
};

const resolveSourceRepo = async (system: PackageSystem, name: string) => {
  const viaDepsDev = await resolveViaDepsDev(system, name);
  if (viaDepsDev !== undefined) return viaDepsDev;
  return resolveViaRegistry(system, name);
};

export const collectDepRepos = async (dir: string): Promise<DepReposReport> => {
  const scan = await collectDepsNames(dir);
  const excluded = scan.localRepos;

  const refs: PackageRef[] = [...scan.npm.map(name => ({ name, system: 'npm' as const })), ...scan.pypi.map(name => ({ name, system: 'pypi' as const }))];
  const resolved = await mapWithConcurrency(refs, RESOLVE_CONCURRENCY, async ref => ({
    ref,
    repo: await resolveSourceRepo(ref.system, ref.name),
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
