import type { ReportRepo } from './reports.ts';

import { describe, expect, test } from './reports.ts';

const seedWorkspaces = async (reports: ReportRepo) => {
  await reports.writePackage('.', 'root-project', {}, { kind: 'infra' });
  await reports.write('pnpm-workspace.yaml', 'packages: ["apps/*", "packages/*", "tests/*"]\n');
  for (const name of ['one', 'two', 'three']) await reports.writePackage(`packages/${name}`, `@acme/${name}`);
};

const findNode = (report: string, label: string) => {
  const node = new RegExp(String.raw`(ws_\d+)\["${label}"\]`, 'u').exec(report)?.[1];
  expect(node).toBeDefined();
  return node;
};

const assertEdge = (report: string, source: string, dependency: string, isType = false) => {
  const end = findNode(report, dependency),
    start = findNode(report, source);
  expect(report).toContain(`${start} ${start}__${end}@${isType ? '-.->' : '-->'} ${end}`);
};

describe('17.1 reading workspace dependencies', () => {
  test.for(['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies'])(
    '17.1.1 draws declared workspace dependencies (%s)',
    async (field, { cz, reports }) => {
      await seedWorkspaces(reports);
      await reports.writePackage('apps/server', '@acme/server', {
        [field]: { '@acme/one': 'workspace:*', external: '1' },
      });
      await reports.writePackage('tests/server', 'server-tests', {}, { is_test: true, kind: 'test' });
      await reports.writePackage('unregistered', 'unknown');
      await cz.run('workspace-graph');
      const report = await reports.graph();
      assertEdge(report, 'server', 'one');
      expect(report).not.toContain('["server-tests"]');
      expect(report).not.toContain('["unknown"]');
      expect(report).not.toContain('["external"]');
    },
  );

  test.for([
    ['import type { Item } from "@acme/one/subpath";', true],
    ['import { type Item } from "@acme/one";', true],
    ['export type { Item } from "@acme/one";', true],
    ['import Item, { type Other } from "@acme/one";', false],
    ['import { type Item, create } from "@acme/one";', false],
    ['const dependency = import("@acme/one");', false],
    ['// import type { Item } from "@acme/one";', false],
  ] as const)(
    '17.1.2 distinguishes type imports from runtime dependencies (%s)',
    async ([source, isType], { cz, reports }) => {
      await seedWorkspaces(reports);
      await reports.writePackage('apps/server', '@acme/server', { dependencies: { '@acme/one': 'workspace:*' } });
      await reports.write('apps/server/src/index.ts', source);
      await reports.write('apps/server/src/index.test.ts', 'import "@acme/one";', { is_test: true });
      await cz.run('workspace-graph');
      assertEdge(await reports.graph(), 'server', 'one', isType);
    },
  );

  test('17.1.3 includes Python requirements and merges dual manifests', async ({ cz, reports }) => {
    await seedWorkspaces(reports);
    await reports.write('pyproject.toml', '[tool.uv.workspace]\nmembers = ["infra/*", "tools/*"]\n', { kind: 'infra' });
    await reports.writePackage('infra/service', '@acme/service', {}, { kind: 'infra' });
    await reports.write('pnpm-workspace.yaml', 'packages: ["infra/*", "packages/*"]\n');
    await reports.write(
      'infra/service/pyproject.toml',
      '[project]\nname = "service"\ndependencies = ["Acme_Util>=1"]\n',
      { kind: 'infra' },
    );
    await reports.write('tools/util/pyproject.toml', '[project]\nname = "acme-util"\n');
    await cz.run('workspace-graph');
    const report = await reports.graph();
    expect(report.match(/\["service"\]/gu)).toHaveLength(1);
    assertEdge(report, 'service', 'acme-util');
    expect(report).toContain('group_infra["infra"]');
  });

  test('17.1.4 includes root projects and Python optional and development requirements', async ({ cz, reports }) => {
    await seedWorkspaces(reports);
    await reports.writePackage(
      '.',
      'root-project',
      { devDependencies: { '@acme/one': 'workspace:*' } },
      { kind: 'infra' },
    );
    await reports.write(
      'pyproject.toml',
      '[project]\nname = "root-python"\n[project.optional-dependencies]\nextra = ["Acme_Util"]\n[dependency-groups]\ndev = ["other", {include-group = "extra"}]\n[tool.uv.workspace]\nmembers = ["tools/*"]\n',
      { kind: 'infra' },
    );
    await reports.write('tools/util/pyproject.toml', '[project]\nname = "acme-util"\n');
    await reports.write('tools/other/pyproject.toml', '[project]\nname = "other"\n');
    await cz.run('workspace-graph');
    const report = await reports.graph();
    assertEdge(report, 'root-project', 'one');
    assertEdge(report, 'root-project', 'acme-util');
    assertEdge(report, 'root-project', 'other');
  });
});

describe('17.2 rendering the shared classification', () => {
  test('17.2.1 uses oracle categories and excludes test workspaces', async ({ cz, reports }) => {
    await reports.write('pnpm-workspace.yaml', 'packages: ["custom/*"]\n');
    for (const kind of ['prod', 'infra', 'demo', 'docs', 'test'] as const) {
      await reports.writePackage(`custom/${kind}`, kind, {}, { is_test: kind === 'test', kind });
    }
    await cz.run('workspace-graph');
    const report = await reports.graph();
    for (const kind of ['prod', 'infra', 'demo', 'docs']) expect(report).toContain(`group_${kind}["${kind}"]`);
    expect(report).not.toContain('["test"]');
  });

  test('17.2.2 lists foundations and keeps reruns deterministic', async ({ cz, reports }) => {
    await seedWorkspaces(reports);
    for (const name of ['alpha', 'beta', 'gamma'])
      await reports.writePackage(`apps/${name}`, `@acme/${name}`, { dependencies: { '@acme/one': 'workspace:*' } });
    await cz.run('workspace-graph');
    const report = await reports.graph();
    expect(report).toContain('## Foundations');
    expect(report).toContain('**`one`** ←');
    await cz.run('workspace-graph');
    expect(await reports.graph()).toBe(report);
  });

  test('17.2.3 respects workspace exclusions and handles empty repositories', async ({ cz, reports }) => {
    await cz.run('workspace-graph');
    expect(await reports.graph()).toContain('No workspace projects are declared.');
    await seedWorkspaces(reports);
    await reports.write('pnpm-workspace.yaml', 'packages: ["packages/*", "!packages/two/**"]\n');
    await cz.run('workspace-graph');
    expect(await reports.graph()).not.toContain('["two"]');
  });

  test('17.2.4 retains the previous report when a manifest is invalid', async ({ cz, reports }) => {
    await seedWorkspaces(reports);
    await reports.write('WORKSPACE_GRAPH.md', 'previous report');
    await reports.write('packages/one/package.json', '{invalid');
    await expect(cz.run('workspace-graph')).rejects.toThrow();
    expect(await reports.graph()).toBe('previous report');
  });
});
