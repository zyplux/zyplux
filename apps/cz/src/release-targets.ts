import { $, ensure, fetchJson, httpOk, parseJson, parseToml, readTrimmed } from '@zyplux/util';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import * as z from 'zod';

const GhcrTokenSchema = z.object({ token: z.string() });
const JsonFieldsSchema = z.record(z.string(), z.unknown());

const VersionSourceSchema = z.union([
  z.object({ file: z.string(), json: z.string() }),
  z.object({ file: z.string(), regex: z.string() }),
]);

const TargetSchema = z.object({
  kind: z.enum(['ghcr', 'npm', 'pypi']),
  label: z.string(),
  surface: z.array(z.string()),
  tag_prefix: z.string(),
  version: VersionSourceSchema,
});

const ManifestSchema = z.object({ target: z.array(TargetSchema) });

export type ReleaseTarget = {
  dir: string;
  isPublished: (version: string) => Promise<boolean>;
  kind: TargetSpec['kind'];
  label: string;
  readVersion: () => Promise<string>;
  tagPrefix: string;
};

type TargetSpec = z.infer<typeof TargetSchema>;
type VersionSource = z.infer<typeof VersionSourceSchema>;

const readVersion = async (repoRoot: string, source: VersionSource) => {
  const text = await readFile(path.join(repoRoot, source.file), 'utf8');
  if ('json' in source) {
    const fields = parseJson(text, JsonFieldsSchema);
    return z.string().parse(fields[source.json]);
  }
  const version = new RegExp(source.regex, 'm').exec(text)?.[1];
  if (version === undefined) {
    throw new Error(`could not read version from ${source.file}`);
  }
  return version;
};

const MANIFEST_MEDIA_TYPES = [
  'application/vnd.oci.image.index.v1+json',
  'application/vnd.oci.image.manifest.v1+json',
  'application/vnd.docker.distribution.manifest.list.v2+json',
  'application/vnd.docker.distribution.manifest.v2+json',
].join(', ');

const fetchGhcrAuth = (repo: string) =>
  fetchJson(`https://ghcr.io/token?scope=repository:${repo}:pull`, GhcrTokenSchema);

const ghcrImagePublished = async (repo: string, tag: string) => {
  const auth = await fetchGhcrAuth(repo);
  if (!auth) return false;
  return httpOk(`https://ghcr.io/v2/${repo}/manifests/${tag}`, {
    headers: {
      Accept: MANIFEST_MEDIA_TYPES,
      Authorization: `Bearer ${auth.token}`,
    },
    method: 'HEAD',
  });
};

const checkPackagePublished = async ({ kind, label }: TargetSpec, version: string) => {
  if (kind === 'npm') {
    return httpOk(`https://registry.npmjs.org/${label.replace('/', '%2f')}/${version}`);
  }
  if (kind === 'pypi') {
    return httpOk(`https://pypi.org/pypi/${label}/${version}/json`);
  }
  return ghcrImagePublished(label.replace(/^ghcr\.io\//, ''), version);
};

export const loadReleaseTargets = async (): Promise<ReleaseTarget[]> => {
  const repoRoot = await readTrimmed($.git.showToplevel());
  const manifest = parseToml(await readFile(path.join(repoRoot, 'release-targets.toml'), 'utf8'), ManifestSchema);
  return manifest.target.map(spec => ({
    dir: path.join(repoRoot, path.dirname(spec.version.file)),
    isPublished: async (version: string) => checkPackagePublished(spec, version),
    kind: spec.kind,
    label: spec.label,
    readVersion: async () => readVersion(repoRoot, spec.version),
    tagPrefix: spec.tag_prefix,
  }));
};

export const resolveReleaseTag = async (tag: string): Promise<{ target: ReleaseTarget; version: string }> => {
  const targets = await loadReleaseTargets();
  const target = targets.find(candidate => tag.startsWith(candidate.tagPrefix));
  ensure(target !== undefined, `no release target in release-targets.toml owns tag '${tag}'`);

  const version = await target.readVersion();
  const expected = `${target.tagPrefix}${version}`;
  ensure(tag === expected, `tag '${tag}' does not match ${target.label} version '${version}' (expected '${expected}')`);

  return { target, version };
};
