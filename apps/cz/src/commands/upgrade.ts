import { ensure } from '@zyplux/util/assert';
import { runPassthrough } from '@zyplux/util/exec';
import { parseJson } from '@zyplux/util/json';
import { $ } from '@zyplux/util/shell';
import { existsSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createInterface } from 'node:readline/promises';
import * as z from 'zod';

import type { InferValue } from '#optique';

import { argument, command, constant, message, multiple, object, option, string } from '#optique';

const DOCKER_AUTH_URL = 'https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/node:pull';
const DOCKER_MANIFEST_URL = 'https://registry-1.docker.io/v2/library/node/manifests/';
const IMAGE_INDEX_TYPES = [
  'application/vnd.oci.image.index.v1+json',
  'application/vnd.docker.distribution.manifest.list.v2+json',
  'application/vnd.oci.image.manifest.v1+json',
  'application/vnd.docker.distribution.manifest.v2+json',
].join(', ');
const MINOR_SEGMENT_COUNT = 2;
const NOT_FOUND_STATUS = 404;
const NODE_INDEX_URL = 'https://nodejs.org/dist/index.json';

const NodeReleaseIndexSchema = z.array(z.object({ version: z.string() }));
const RegistryTokenSchema = z.object({ token: z.string() });
const RegistryDigestSchema = z.string();
const NpmLatestSchema = z.object({ version: z.string() });
const RuntimeSchema = z.object({ name: z.literal('node'), version: z.string() });
const DevEnginesSchema = z.object({ runtime: RuntimeSchema });
const ToolchainSchema = z.object({ turbo: z.string() });
const UpgradeManifestSchema = z.object({
  devEngines: DevEnginesSchema,
  packageManager: z.string(),
  toolchain: ToolchainSchema.optional(),
});

const packageArgument = multiple(
  argument(string({ metavar: 'PACKAGE' }), {
    description: message`Optional package selector passed to pnpm update. Repeatable.`,
  }),
);

export const upgradeCommand = command(
  'upgrade',
  object({
    command: constant('upgrade' as const),
    interactive: option('--interactive', {
      description: message`Ask before changing toolchain pins and select dependency updates interactively.`,
    }),
    packages: packageArgument,
  }),
  {
    aliases: ['up'],
    brief: message`Upgrade the pinned toolchain plus JavaScript and Python workspace dependencies.`,
  },
);

type UpgradeConfig = InferValue<typeof upgradeCommand>;
type UpgradeManifest = z.infer<typeof UpgradeManifestSchema>;

const fetchJson = async (url: string) => {
  const response = await fetch(url);
  ensure(response.ok, `${url} returned ${response.status}`);
  return response.json();
};

const fetchImageDigest = async (tag: string, token: string) => {
  const response = await fetch(`${DOCKER_MANIFEST_URL}${tag}`, {
    headers: { Accept: IMAGE_INDEX_TYPES, Authorization: `Bearer ${token}` },
    method: 'HEAD',
  });
  if (response.status === NOT_FOUND_STATUS) return;
  ensure(response.ok, `Docker registry returned ${response.status} for node:${tag}`);
  const digest = response.headers.get('docker-content-digest');
  return RegistryDigestSchema.parse(digest);
};

const versionMajor = (version: string) => {
  const [major] = version.replace(/^v/u, '').split('.', 1);
  ensure(major !== undefined && /^\d+$/u.test(major), `invalid version '${version}'`);
  return major;
};

const fetchLatestDeployableNode = async (declared: string) => {
  const [releaseJson, tokenJson] = await Promise.all([fetchJson(NODE_INDEX_URL), fetchJson(DOCKER_AUTH_URL)]);
  const releases = NodeReleaseIndexSchema.parse(releaseJson);
  const { token } = RegistryTokenSchema.parse(tokenJson);
  const declaredMajor = versionMajor(declared);
  for (const release of releases) {
    const version = release.version.replace(/^v/u, '');
    if (versionMajor(version) !== declaredMajor) continue;
    if ((await fetchImageDigest(`${version}-slim`, token)) !== undefined) return version;
  }
  throw new Error(`no Node ${declaredMajor} release has a matching official slim image`);
};

const fetchLatestTurbo = async () =>
  NpmLatestSchema.parse(await fetchJson('https://registry.npmjs.org/turbo/latest')).version;

const minorOf = (version: string) => version.split('.').slice(0, MINOR_SEGMENT_COUNT).join('.');

const loadManifest = async (root: string) => {
  const manifestText = await readFile(path.join(root, 'package.json'), 'utf8');
  return parseJson(manifestText, UpgradeManifestSchema);
};

const shouldUpgrade = async (tool: string, declared: string, latest: string) => {
  const prompt = createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = await prompt.question(`upgrade ${tool} from ${declared} to ${latest}? [y/N] `);
    return answer.trim().toLowerCase() === 'y';
  } finally {
    prompt.close();
  }
};

const listDockerfiles = async (root: string) => {
  const output = await $.git.lsFiles(root, ['*Dockerfile*']);
  return output.stdout
    .toString()
    .split('\0')
    .filter(file => file.length > 0);
};

const syncImageNode = async (root: string, version: string) => {
  const dockerfiles = await listDockerfiles(root);
  for (const file of dockerfiles) {
    const filePath = path.join(root, file);
    const content = await readFile(filePath, 'utf8');
    const updated = content.replaceAll(/^ARG NODE_VERSION=.+$/gmu, () => `ARG NODE_VERSION=${version}`);
    if (updated !== content) await writeFile(filePath, updated);
  }
};

const packageManagerMajor = ({ packageManager }: UpgradeManifest) => {
  const match = /^pnpm@(\d+)/u.exec(packageManager);
  ensure(match?.[1] !== undefined, `packageManager must pin pnpm, found '${packageManager}'`);
  return match[1];
};

const syncNode = async (root: string, declared: string, latest: string, isInteractive: boolean) => {
  const hasUpdate = declared !== latest;
  console.log(`node: declared ${declared}, latest deployable ${latest} — ${hasUpdate ? 'NEW VERSION' : 'up to date'}`);
  if (!hasUpdate || (isInteractive && !(await shouldUpgrade('Node', declared, latest)))) return;
  await runPassthrough(['pnpm', 'runtime', 'set', 'node', latest], root);
  await syncImageNode(root, latest);
};

const syncTurbo = async (
  root: string,
  declared: string | undefined,
  latest: string | undefined,
  isInteractive: boolean,
) => {
  if (declared === undefined || latest === undefined) return;
  const target = minorOf(latest);
  const hasUpdate = declared !== target;
  console.log(
    `turbo: declared ${declared}, latest ${latest} — ${hasUpdate ? `NEW VERSION ${target}` : `up to date; ${declared}.x floats on install`}`,
  );
  if (!hasUpdate || (isInteractive && !(await shouldUpgrade('turbo', declared, target)))) return;
  await runPassthrough(['pnpm', 'pkg', 'set', `toolchain.turbo=${target}`], root);
};

const updateJavaScript = (root: string, packages: readonly string[], isInteractive: boolean) =>
  runPassthrough(
    [
      'pnpm',
      'update',
      '--recursive',
      '--include-workspace-root',
      '--latest',
      ...(isInteractive ? ['--interactive'] : []),
      ...packages,
    ],
    root,
  );

const updatePython = async (root: string) => {
  if (!existsSync(path.join(root, 'pyproject.toml'))) return;
  await runPassthrough(['uv', 'lock', '--upgrade'], root);
  await runPassthrough(['uvx', 'uv-bump', '-v'], root);
  await runPassthrough(['uv', 'sync', '--all-packages', '--all-groups'], root);
};

export const runUpgrade = async ({ interactive, packages }: UpgradeConfig) => {
  const root = process.cwd();
  const manifest = await loadManifest(root);
  const [latestNode, latestTurbo] = await Promise.all([
    fetchLatestDeployableNode(manifest.devEngines.runtime.version),
    manifest.toolchain === undefined ? undefined : fetchLatestTurbo(),
  ]);
  const declaredNode = manifest.devEngines.runtime.version;
  const declaredTurbo = manifest.toolchain?.turbo;
  await runPassthrough(['pnpm', 'self-update', packageManagerMajor(manifest)], root);
  await syncNode(root, declaredNode, latestNode, interactive);
  await syncTurbo(root, declaredTurbo, latestTurbo, interactive);
  await updateJavaScript(root, packages, interactive);
  await updatePython(root);
};
