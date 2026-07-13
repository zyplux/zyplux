import { describe, expect, test } from '#fixtures';

test.override({ ruleName: 'fixture-role-imports' });

const options = [{ subject: '@demo/app' }];

describe('20.1 confining the subject to arrange and act', () => {
  test('20.1.1 fails a fixture module other than arrange or act importing the subject', ({ lintRule }) => {
    expect(lintRule("import { run } from '@demo/app';", { options })).toReport('subjectOutsideRole');
  });

  test('20.1.2 fails a fixture module importing a subject subpath', ({ lintRule }) => {
    expect(lintRule("import { helper } from '@demo/app/internals/helper';", { options })).toReport(
      'subjectOutsideRole',
    );
  });

  test('20.1.3 fails a fixture module re-exporting from the subject', ({ lintRule }) => {
    expect(lintRule("export { run } from '@demo/app';", { options })).toReport('subjectOutsideRole');
  });

  test('20.1.4 fails a fixture module star-exporting the subject', ({ lintRule }) => {
    expect(lintRule("export * from '@demo/app';", { options })).toReport('subjectOutsideRole');
  });

  test('20.1.5 fails a fixture module dynamically importing the subject', ({ lintRule }) => {
    expect(lintRule("export const loadRun = () => import('@demo/app');", { options })).toReport('subjectOutsideRole');
  });

  test("20.1.6 allows any fixture module to import the subject's contracts seam", ({ lintRule }) => {
    expect(lintRule("import { WidgetSchema } from '@demo/app/contracts';", { options })).toReportNothing();
  });

  test('20.1.7 allows a fixture module to import an unrelated package', ({ lintRule }) => {
    expect(lintRule("import { parseWidgets } from '@demo/util';", { options })).toReportNothing();
  });
});

describe("20.2 wiring the subject option from each suite's manifest", () => {
  test("20.2.1 resolves this suite's own subject package from its package.json", ({ zyplux }) => {
    const config = zyplux();
    const entry = config.find(
      candidate =>
        Array.isArray(candidate.files) && candidate.files.includes('tests/eslint-config/fixtures/*.{ts,tsx}'),
    );
    expect(entry?.rules?.['@zyplux/fixture-role-imports']).toEqual(['error', { subject: '@zyplux/eslint-config' }]);
    expect(entry?.ignores).toEqual(['tests/eslint-config/fixtures/{arrange,act}.{ts,tsx}']);
  });

  test('20.2.2 pairs a suite by workspace directory, not by its own package name', ({ zyplux }) => {
    const config = zyplux();
    const entry = config.find(
      candidate => Array.isArray(candidate.files) && candidate.files.includes('tests/util-ts/fixtures/*.{ts,tsx}'),
    );
    expect(entry?.rules?.['@zyplux/fixture-role-imports']).toEqual(['error', { subject: '@zyplux/util' }]);
  });
});
