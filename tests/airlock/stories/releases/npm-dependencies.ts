import type { ShellFake } from '@zyplux/spectra/shell-fake';
import type { TempDir } from '@zyplux/spectra/temp-directory';

import { ensure } from '@zyplux/util/assert';
import { execFileSync } from 'node:child_process';

import type { SeededTargets } from './release-scenario.ts';

type NpmConsumerContext = {
  loadArtifact: (relativePath: string) => Promise<string>;
  shell: ShellFake;
  targets: SeededTargets;
  tempDir: TempDir;
};

const buildWorkspace = ({ dir, label, version }: SeededTargets['util']) => ({
  name: label,
  path: dir,
  private: false,
  version,
});

export const createDependencyWorkspace = async ({ loadArtifact, shell, targets, tempDir }: NpmConsumerContext) => {
  const consumer = {
    ...targets.util,
    dir: `${tempDir.path}/packages/consumer`,
    label: '@zyplux/consumer',
    tag: 'consumer-v1.2.3',
  };
  const independent = {
    ...targets.util,
    dir: `${tempDir.path}/packages/independent`,
    label: '@zyplux/independent',
    tag: 'independent-v1.2.3',
  };
  const manifest = await loadArtifact('airlock-targets.toml');
  await tempDir.write(
    'airlock-targets.toml',
    manifest.replace(
      '[util]',
      '[consumer]\nkind = "npm"\nsurface = []\nversion = { file = "packages/consumer/package.json", json = "version" }\n\n[independent]\nkind = "npm"\nsurface = []\nversion = { file = "packages/independent/package.json", json = "version" }\n\n[util]',
    ),
  );
  await tempDir.write(
    'packages/consumer/package.json',
    JSON.stringify({
      dependencies: { '@zyplux/util': 'workspace:*' },
      name: consumer.label,
      version: consumer.version,
    }),
  );
  await tempDir.write('packages/consumer/CHANGELOG.md', '# Consumer\n\n## 1.2.3\n\n- Publish consumer.\n');
  await tempDir.write(
    'packages/independent/package.json',
    JSON.stringify({ name: independent.label, version: independent.version }),
  );
  await tempDir.write('packages/independent/CHANGELOG.md', '# Independent\n\n## 1.2.3\n\n- Publish independently.\n');
  shell.on(
    'pnpm list',
    JSON.stringify([buildWorkspace(consumer), buildWorkspace(independent), buildWorkspace(targets.util)]),
  );
  return consumer;
};

export const createBundledConsumer = async (context: NpmConsumerContext) => {
  const { shell, targets, tempDir } = context;
  const consumer = await createDependencyWorkspace(context);
  const implementation = {
    name: '@zyplux/implementation',
    path: `${tempDir.path}/packages/implementation`,
    private: true,
    version: '1.0.0',
  };
  await tempDir.write('package.json', '{"name":"release-fixture","private":true,"version":"0.0.0"}');
  await tempDir.write('pnpm-workspace.yaml', 'packages:\n  - packages/*\n');
  await tempDir.write('packages/implementation/package.json', JSON.stringify(implementation));
  await tempDir.write(
    'packages/consumer/package.json',
    JSON.stringify({
      dependencies: { [implementation.name]: 'workspace:*' },
      name: consumer.label,
      version: consumer.version,
    }),
  );
  await tempDir.write(
    '.pnpmfile.mjs',
    `export const hooks = { beforePacking(manifest) { delete manifest.dependencies['${implementation.name}']; return manifest; } };`,
  );
  shell.on('pnpm list', JSON.stringify([buildWorkspace(consumer), buildWorkspace(targets.util), implementation]));
  const runPacking = () => {
    const call = shell.calls.at(-1);
    ensure(call !== undefined, 'packing command must be recorded');
    return execFileSync(call.program, call.argv, { cwd: call.cwd, encoding: 'utf8' });
  };
  shell.on('pnpm pack', runPacking);
  shell.on('tar -xOf', runPacking);
  return consumer;
};
