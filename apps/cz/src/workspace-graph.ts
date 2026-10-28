import type * as z from 'zod';

import { ensure } from '@zyplux/util/assert';
import { PackageJsonSchema, WorkspaceConfigSchema } from '@zyplux/util/contracts';
import { parseJson } from '@zyplux/util/json';
import { normalizePythonName, pythonRequirementNames } from '@zyplux/util/manifest';
import { collectModuleReferences } from '@zyplux/util/module-references';
import { parseToml } from '@zyplux/util/toml';
import { existsSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import ts from 'typescript';
import { parse as parseYaml } from 'yaml';

import type { SourceSnapshot } from './contracts.ts';

import { PythonWorkspaceManifestSchema } from './contracts.ts';
import { calcEdgeColor } from './edge-palette.ts';
import { loadSourceSnapshot } from './source-oracle.ts';

type SourceFiles = SourceSnapshot;
type Workspace = {
  dependencies: Set<string>;
  directory: string;
  kind: string;
  label: string;
  typeDependencies: Set<string>;
};

const REPORT_NAME = 'WORKSPACE_GRAPH.md';
const FOUNDATION_RATIO = 0.4;
const TS_SUFFIXES = new Set(['.cts', '.mts', '.ts', '.tsx']);

const isWorkspaceMember = (directory: string, globs: readonly string[]) => {
  const isMatch = (glob: string) => path.posix.matchesGlob(directory, glob.replace(/\/$/u, ''));
  return (
    globs.some(glob => !glob.startsWith('!') && isMatch(glob)) &&
    globs.every(
      glob => !(glob.startsWith('!') && (isMatch(glob.slice(1)) || isMatch(glob.slice(1).replace(/\/\*\*$/u, '')))),
    )
  );
};

const listMembers = (files: SourceFiles, manifest: string, globs: readonly string[]) =>
  Object.entries(files).flatMap(([file, source]) => {
    if (source.is_test || path.posix.basename(file) !== manifest) return [];
    const directory = path.posix.dirname(file);
    return directory === '.' || isWorkspaceMember(directory, globs) ? directory : [];
  });

const loadTypeDependencies = async (root: string, files: SourceFiles, npm: Map<string, Workspace>) => {
  const imports = new Map<Workspace, Map<string, Set<boolean>>>();
  const owners = new Set(npm.values())
    .values()
    .toArray()
    .toSorted((a, b) => b.directory.length - a.directory.length);
  for (const [file, classification] of Object.entries(files)) {
    if (classification.is_test || !TS_SUFFIXES.has(path.extname(file))) continue;
    const owner = owners.find(workspace => workspace.directory === '.' || file.startsWith(`${workspace.directory}/`));
    if (owner === undefined) continue;
    const content = await readFile(path.join(root, file), 'utf8');
    const source = ts.createSourceFile(file, content, ts.ScriptTarget.Latest, true);
    for (const reference of collectModuleReferences(source)) {
      const provider = [...npm].find(
        ([name]) => reference.specifier === name || reference.specifier.startsWith(`${name}/`),
      )?.[1];
      if (provider === undefined) continue;
      let edges = imports.get(owner);
      if (edges === undefined) {
        edges = new Map();
        imports.set(owner, edges);
      }
      let bindings = edges.get(provider.directory);
      if (bindings === undefined) {
        bindings = new Set();
        edges.set(provider.directory, bindings);
      }
      bindings.add(reference.hasTypeBindings && !reference.hasValueBindings);
    }
  }
  for (const [workspace, edges] of imports) {
    workspace.typeDependencies = new Set(
      [...edges].filter(([, kinds]) => kinds.size === 1 && kinds.has(true)).map(([directory]) => directory),
    );
  }
};

const loadWorkspaces = async (root: string, files: SourceFiles) => {
  const npm = new Map<string, Workspace>();
  const python = new Map<string, Workspace>();
  const members = new Map<string, Workspace>();
  const npmManifests = new Map<string, z.infer<typeof PackageJsonSchema>>();
  const pythonManifests = new Map<string, z.infer<typeof PythonWorkspaceManifestSchema>>();
  const pnpmPath = path.join(root, 'pnpm-workspace.yaml');
  const pnpm = existsSync(pnpmPath)
    ? WorkspaceConfigSchema.parse(parseYaml(await readFile(pnpmPath, 'utf8')))
    : { packages: [] };
  const getMember = (directory: string, label: string, manifest: string) => {
    let member = members.get(directory);
    if (member === undefined) {
      const key = directory === '.' ? manifest : `${directory}/${manifest}`;
      const classification = files[key];
      ensure(classification !== undefined, `missing source classification for ${key}`);
      member = {
        dependencies: new Set<string>(),
        directory,
        kind: classification.kind,
        label,
        typeDependencies: new Set<string>(),
      };
      members.set(directory, member);
    }
    return member;
  };
  for (const directory of listMembers(files, 'package.json', pnpm.packages)) {
    const manifest = parseJson(await readFile(path.join(root, directory, 'package.json'), 'utf8'), PackageJsonSchema);
    if (manifest.name === undefined) continue;
    npmManifests.set(directory, manifest);
    npm.set(manifest.name, getMember(directory, manifest.name.split('/').at(-1) ?? manifest.name, 'package.json'));
  }
  const pythonPath = path.join(root, 'pyproject.toml');
  const pyproject = existsSync(pythonPath)
    ? parseToml(await readFile(pythonPath, 'utf8'), PythonWorkspaceManifestSchema)
    : undefined;
  const uvWorkspace = pyproject?.tool?.uv?.workspace;
  const globs = [...(uvWorkspace?.members ?? []), ...(uvWorkspace?.exclude ?? []).map(glob => `!${glob}`)];
  for (const directory of listMembers(files, 'pyproject.toml', globs)) {
    const manifest = parseToml(
      await readFile(path.join(root, directory, 'pyproject.toml'), 'utf8'),
      PythonWorkspaceManifestSchema,
    );
    if (manifest.project?.name === undefined) continue;
    pythonManifests.set(directory, manifest);
    python.set(
      normalizePythonName(manifest.project.name) ?? manifest.project.name,
      getMember(directory, manifest.project.name, 'pyproject.toml'),
    );
  }
  for (const [directory, manifest] of npmManifests) {
    const member = members.get(directory);
    const dependencyGroups = [
      manifest.dependencies,
      manifest.devDependencies,
      manifest.optionalDependencies,
      manifest.peerDependencies,
    ];
    for (const dependencies of dependencyGroups) {
      const names = Object.keys(dependencies ?? {});
      for (const name of names) {
        const dependency = npm.get(name);
        if (member !== undefined && dependency !== undefined && member !== dependency)
          member.dependencies.add(dependency.directory);
      }
    }
  }
  for (const [directory, manifest] of pythonManifests) {
    const member = members.get(directory);
    for (const name of pythonRequirementNames(manifest)) {
      const dependency = python.get(name);
      if (member !== undefined && dependency !== undefined && member !== dependency)
        member.dependencies.add(dependency.directory);
    }
  }
  await loadTypeDependencies(root, files, npm);
  return members
    .values()
    .toArray()
    .toSorted((a, b) => a.directory.localeCompare(b.directory));
};

const quoteLabel = (label: string) =>
  label.replaceAll('&', '&amp;').replaceAll('"', '#quot;').replaceAll('<', '&lt;').replaceAll(']', '#93;');

const buildReport = (members: Workspace[]) => {
  if (members.length === 0) return '# Workspace Dependency Graph\n\nNo workspace projects are declared.\n';
  const ids = new Map(members.map((member, index) => [member.directory, `ws_${index}`]));
  const foundations = new Set(
    members
      .filter(
        member =>
          members.filter(importer => importer.dependencies.has(member.directory)).length >=
          members.length * FOUNDATION_RATIO,
      )
      .map(member => member.directory),
  );
  const lines = [
    '# Workspace Dependency Graph',
    '',
    '*Which workspace projects depend on each other?*',
    '',
    '```mermaid',
    '---',
    'config:',
    '  theme: dark',
    '  layout: elk',
    '---',
    'flowchart LR',
  ];
  const groups = [...new Set(members.map(member => member.kind))].toSorted((a, b) => a.localeCompare(b));
  for (const group of groups) {
    lines.push(`    subgraph group_${group}["${group}"]`);
    for (const member of members) {
      if (member.kind !== group) continue;
      lines.push(
        `        ${ids.get(member.directory)}["${quoteLabel(member.label)}"]${foundations.has(member.directory) ? ':::foundation' : ''}`,
      );
    }
    lines.push('    end');
  }
  const products = members.filter(member => member.kind === 'prod');
  for (const member of members) {
    const edgeIds: string[] = [];
    const dependencies = [...member.dependencies]
      .filter(directory => !foundations.has(directory))
      .toSorted((a, b) => a.localeCompare(b));
    for (const dependency of dependencies) {
      const end = ids.get(dependency),
        start = ids.get(member.directory);
      const edgeId = `${start}__${end}`;
      lines.push(`    ${start} ${edgeId}@${member.typeDependencies.has(dependency) ? '-.->' : '-->'} ${end}`);
      edgeIds.push(edgeId);
    }
    if (edgeIds.length === 0 || member.kind !== 'prod') continue;
    const style = `${ids.get(member.directory)}_edges`;
    lines.push(
      `    classDef ${style} stroke:${calcEdgeColor(products.indexOf(member), products.length)},stroke-width:2px`,
      `    class ${edgeIds.join(',')} ${style}`,
    );
  }
  lines.push(
    '    classDef foundation fill:#2b2b2b,stroke:#888,stroke-dasharray:5 5',
    '```',
    '',
    'Solid arrows are declared workspace dependencies; dashed arrows have only type imports in TypeScript source.',
    '',
  );
  if (foundations.size > 0) {
    lines.push(
      '## Foundations',
      '',
      `Imported by at least 40% of workspaces (${Math.ceil(members.length * FOUNDATION_RATIO)}/${members.length}):`,
      '',
    );
    for (const member of members) {
      if (!foundations.has(member.directory)) continue;
      const importers = members
        .filter(importer => importer.dependencies.has(member.directory))
        .map(
          importer => `\`${importer.label}\`${importer.typeDependencies.has(member.directory) ? ' (type-only)' : ''}`,
        );
      lines.push(`- **\`${member.label}\`** ← ${importers.join(', ')}`);
    }
    lines.push('');
  }
  lines.push('Generate with `cz workspace-graph`.', '');
  return lines.join('\n');
};

export const writeWorkspaceGraph = async (directory: string) => {
  const { files, root } = await loadSourceSnapshot(directory);
  const members = await loadWorkspaces(root, files);
  const destination = path.join(root, REPORT_NAME);
  await writeFile(destination, buildReport(members));
  return destination;
};
