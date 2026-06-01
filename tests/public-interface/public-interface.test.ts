import { plugin, totvibe } from '@totvibe/eslint-config';
import { describe, expect, test } from 'bun:test';

type Config = ReturnType<typeof totvibe>;

const customRuleNames = ['no-inferrable-return-type', 'no-type-predicate', 'no-zod-custom', 'prefer-arrow-functions'];

const hasReactSettings = (config: Config) =>
  config.some(entry => entry.settings !== undefined && 'react' in entry.settings);

const hasRouteRule = (config: Config) =>
  config.some(entry => Array.isArray(entry.files) && entry.files.includes('**/routes/**/*.{ts,tsx}'));

const reactVersion = (config: Config) => {
  for (const entry of config) {
    const settings = entry.settings;
    if (settings === undefined || !('react' in settings)) continue;
    const react = settings.react;
    if (react !== null && typeof react === 'object' && 'version' in react) return react.version;
  }
  return;
};

const findEntryRule = (config: Config, offSignatureRule: string, targetRule: string) => {
  const entry = config.find(item => item.rules?.[offSignatureRule] === 'off');
  return entry?.rules?.[targetRule];
};

const turnsOffRule = (config: Config, ruleName: string) => config.some(entry => entry.rules?.[ruleName] === 'off');

describe('totvibe', () => {
  test('returns a non-empty flat config array', () => {
    expect(totvibe().length).toBeGreaterThan(0);
  });

  test('registers the @totvibe plugin and its rules', () => {
    const config = totvibe();
    const entry = config.find(item => item.plugins !== undefined && '@totvibe' in item.plugins);
    expect(entry).toBeDefined();
    expect(Object.keys(entry?.rules ?? {})).toEqual(customRuleNames.map(name => `@totvibe/${name}`));
  });

  test('React config is opt-in', () => {
    expect(hasReactSettings(totvibe())).toBe(false);
    expect(hasReactSettings(totvibe({ react: true }))).toBe(true);
  });

  test('TanStack route rule is opt-in', () => {
    expect(hasRouteRule(totvibe())).toBe(false);
    expect(hasRouteRule(totvibe({ tanstack: true }))).toBe(true);
  });

  test('reactVersion defaults to detect and passes a pinned version through', () => {
    expect(reactVersion(totvibe({ react: true }))).toBe('detect');
    expect(reactVersion(totvibe({ react: true, reactVersion: '19.0' }))).toBe('19.0');
  });

  test('filenameCase is unset by default and relaxes to camel/kebab/pascal with react', () => {
    expect(findEntryRule(totvibe(), 'unicorn/prevent-abbreviations', 'unicorn/filename-case')).toBeUndefined();
    expect(findEntryRule(totvibe({ react: true }), 'unicorn/prevent-abbreviations', 'unicorn/filename-case')).toEqual([
      'error',
      { cases: { camelCase: true, kebabCase: true, pascalCase: true } },
    ]);
  });

  test('filenameCase passes an explicit case map through', () => {
    const config = totvibe({ filenameCase: { snakeCase: true } });
    expect(findEntryRule(config, 'unicorn/prevent-abbreviations', 'unicorn/filename-case')).toEqual([
      'error',
      { cases: { snakeCase: true } },
    ]);
  });

  test('nonDomReactFiles requires react and turns off react/no-unknown-property', () => {
    expect(turnsOffRule(totvibe(), 'react/no-unknown-property')).toBe(false);
    expect(turnsOffRule(totvibe({ nonDomReactFiles: ['apps/tui/**'] }), 'react/no-unknown-property')).toBe(false);
    expect(turnsOffRule(totvibe({ nonDomReactFiles: ['apps/tui/**'], react: true }), 'react/no-unknown-property')).toBe(
      true,
    );
  });
});

describe('plugin', () => {
  test('exposes the custom rules', () => {
    expect(Object.keys(plugin.rules).toSorted()).toEqual(customRuleNames.toSorted());
  });
});
