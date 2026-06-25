import { object } from '@optique/core/constructs';
import { message } from '@optique/core/message';
import { command, constant } from '@optique/core/primitives';
import { parseJson, readJson } from '@zyplux/util';
import { $, readTrimmed } from '@zyplux/util/shell';
import { readdir } from 'node:fs/promises';
import path from 'node:path';
import { z } from 'zod';

const ORG = 'zyplux';
const RULESETS_DIR = '.github/rulesets';

const RulesetSummariesSchema = z.array(z.object({ id: z.number(), name: z.string() }));
const RulesetFileSchema = z.object({ name: z.string() });

export const applyOrgRulesetsCommand = command(
  'apply-org-rulesets',
  object({ command: constant('apply-org-rulesets' as const) }),
  {
    brief: message`Upsert every org ruleset under .github/rulesets/ to GitHub as the source of truth.`,
  },
);

const listOrgRulesets = async () =>
  parseJson(await readTrimmed($.gh.api(`orgs/${ORG}/rulesets`, { paginate: true })), RulesetSummariesSchema);

export const runApplyOrgRulesets = async () => {
  const entries = await readdir(RULESETS_DIR);
  const files = entries.filter(name => name.endsWith('.json')).toSorted((a, b) => a.localeCompare(b));
  const live = await listOrgRulesets();

  for (const file of files) {
    const filePath = path.join(RULESETS_DIR, file);
    const { name } = await readJson(filePath, RulesetFileSchema);
    const match = live.find(ruleset => ruleset.name === name);

    if (match === undefined) {
      await $.gh.api(`orgs/${ORG}/rulesets`, { input: filePath, method: 'POST' });
      console.log(`created org ruleset '${name}'`);
    } else {
      await $.gh.api(`orgs/${ORG}/rulesets/${match.id}`, { input: filePath, method: 'PUT' });
      console.log(`updated org ruleset '${name}' (#${match.id})`);
    }
  }
};
