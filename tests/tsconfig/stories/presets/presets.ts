import { libraryTest } from '@zyplux/spectra/library-test-api';
import { LooseRecordSchema } from '@zyplux/util/contracts';
import { parseJson } from '@zyplux/util/json';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as z from 'zod';

const configDir = fileURLToPath(new URL('../../../../packages/tsconfig', import.meta.url));
const TsconfigSchema = z.object({ compilerOptions: LooseRecordSchema });
const EmitPolicySchema = z.object({
  declarationMap: z.boolean(),
  emitDeclarationOnly: z.boolean(),
  outDir: z.string(),
  rewriteRelativeImportExtensions: z.boolean().default(false),
  tsBuildInfoFile: z.string(),
});
const BasePolicySchema = EmitPolicySchema.extend({ composite: z.boolean() });
const ModulePolicySchema = z.object({ module: z.string(), moduleResolution: z.string() });

const loadCompilerOptions = (preset: string) =>
  parseJson(readFileSync(path.join(configDir, `${preset}.json`), 'utf8'), TsconfigSchema).compilerOptions;

const loadTsconfigPresets = () => {
  const base = loadCompilerOptions('base');
  return {
    base: BasePolicySchema.parse(base),
    baseDeclaresModules: 'module' in base || 'moduleResolution' in base,
    nodePub: EmitPolicySchema.parse(loadCompilerOptions('node-pub')),
    variants: Object.fromEntries(
      ['bun', 'cfworker', 'node', 'tui', 'web'].map(name => [
        name,
        ModulePolicySchema.parse(loadCompilerOptions(name)),
      ]),
    ),
  };
};

export const test = libraryTest.extend('tsconfigPresets', () => loadTsconfigPresets());
export { describe, expect } from 'vitest';
