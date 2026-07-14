import { PrintedConfigSchema } from '@zyplux/eslint-config/contracts';
import { readJsonSync } from '@zyplux/util';
import { fileURLToPath } from 'node:url';

export const suiteDir = fileURLToPath(new URL('../', import.meta.url));

export const eslintConfigDir = fileURLToPath(new URL('../../../packages/eslint-config/', import.meta.url));

export type RuleLintOptions = { filename?: string; options?: unknown[] };

const rulesSnapshotUrl = new URL('../../../packages/eslint-config/rules.json', import.meta.url);

export const loadRulesSnapshot = () => readJsonSync(rulesSnapshotUrl, PrintedConfigSchema);
