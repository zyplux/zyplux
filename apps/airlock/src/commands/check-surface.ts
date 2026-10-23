import type { InferValue } from '@optique/core';

import { command, constant, message, object, option, optional, string } from '@optique/core';
import { ensure } from '@zyplux/util/assert';

import { checkReleaseSurface } from '#release-surface';

const baseOption = optional(option('--base', string({ metavar: 'REF' })));

export const checkSurfaceCommand = command(
  'check-surface',
  object({
    base: baseOption,
    command: constant('check-surface' as const),
    json: option('--json'),
  }),
  { brief: message`Require single-step version bumps for changed release surfaces.` },
);

export const runCheckSurface = async ({ base, json }: InferValue<typeof checkSurfaceCommand>) => {
  const branch = process.env['GITHUB_BASE_REF'];
  const findings = await checkReleaseSurface(base ?? (branch ? `origin/${branch}` : undefined));
  if (json) console.log(JSON.stringify(findings));
  else for (const finding of findings) console.log(`${finding.status}: ${finding.message}`);
  ensure(
    findings.every(finding => finding.status === 'pass' || finding.status === 'skip'),
    'release surface validation failed',
  );
};
