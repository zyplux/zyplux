import { plugin, zyplux } from '@zyplux/eslint-config';
import { describe, expect, test } from 'vitest';

type Config = ReturnType<typeof zyplux>;

const hasReactSettings = (config: Config) =>
  config.some(entry => entry.settings !== undefined && 'react' in entry.settings);

const hasRouteRule = (config: Config) =>
  config.some(entry => Array.isArray(entry.files) && entry.files.includes('**/routes/**/*.{ts,tsx}'));

const reactVersion = (config: Config) => {
  for (const entry of config) {
    const { settings } = entry;
    if (settings === undefined || !('react' in settings)) continue;
    const { react } = settings;
    if (react !== null && typeof react === 'object' && 'version' in react) return react.version;
  }
  return;
};

const isRuleDisabled = (config: Config, ruleName: string) => config.some(entry => entry.rules?.[ruleName] === 'off');

const reactSettingsFiles = (config: Config) =>
  config.flatMap(entry => (entry.settings !== undefined && 'react' in entry.settings ? (entry.files ?? []) : []));

const offRuleFiles = (config: Config, ruleName: string) =>
  config.flatMap(entry => (entry.rules?.[ruleName] === 'off' ? (entry.files ?? []) : []));

describe('zyplux', () => {
  test('returns a non-empty flat config array', () => {
    expect(zyplux().length).toBeGreaterThan(0);
  });

  test('enables exactly the rules the @zyplux plugin exports', () => {
    const config = zyplux();
    const entry = config.find(item => item.plugins !== undefined && '@zyplux' in item.plugins);
    expect(entry).toBeDefined();
    const exported = Object.keys(plugin.rules).toSorted((a, b) => a.localeCompare(b));
    const enabled = Object.keys(entry?.rules ?? {})
      .map(name => name.replace('@zyplux/', ''))
      .toSorted((a, b) => a.localeCompare(b));
    expect(exported.length).toBeGreaterThan(0);
    expect(enabled).toEqual(exported);
  });

  test('vitest rules are enabled and scoped to test files', () => {
    const config = zyplux();
    const entry = config.find(item => item.plugins !== undefined && 'vitest' in item.plugins);
    expect(entry).toBeDefined();
    expect(entry?.files).toEqual(['**/*.{test,spec}.{ts,tsx}']);
    const vitestRules = Object.keys(entry?.rules ?? {}).filter(name => name.startsWith('vitest/'));
    expect(vitestRules.length).toBeGreaterThan(0);
  });

  test('React config is opt-in', () => {
    expect(hasReactSettings(zyplux())).toBe(false);
    expect(hasReactSettings(zyplux({ react: true }))).toBe(true);
  });

  test('TanStack route rule is opt-in', () => {
    expect(hasRouteRule(zyplux())).toBe(false);
    expect(hasRouteRule(zyplux({ tanstack: true }))).toBe(true);
  });

  test('reactVersion defaults to detect and passes a pinned version through', () => {
    expect(reactVersion(zyplux({ react: true }))).toBe('detect');
    expect(reactVersion(zyplux({ react: true, reactVersion: '19.0' }))).toBe('19.0');
  });

  test('nonDomReactFiles requires react and turns off react/no-unknown-property', () => {
    expect(isRuleDisabled(zyplux(), 'react/no-unknown-property')).toBe(false);
    expect(isRuleDisabled(zyplux({ nonDomReactFiles: ['apps/tui/**'] }), 'react/no-unknown-property')).toBe(false);
    expect(
      isRuleDisabled(zyplux({ nonDomReactFiles: ['apps/tui/**'], react: true }), 'react/no-unknown-property'),
    ).toBe(true);
  });
});

describe('renderer presets', () => {
  test('react: true scopes the DOM preset to the default src glob', () => {
    expect(reactSettingsFiles(zyplux({ react: true }))).toEqual(['**/src/**/*.{ts,tsx}']);
  });

  test('a renderer map scopes each renderer to its own globs', () => {
    const config = zyplux({ react: { dom: ['apps/web/**/*.tsx'], opentui: ['apps/tui/**/*.tsx'] } });
    expect(reactSettingsFiles(config)).toEqual(['apps/web/**/*.tsx', 'apps/tui/**/*.tsx']);
  });

  test('the DOM renderer keeps react/no-unknown-property; non-DOM renderers turn it off on their globs', () => {
    const config = zyplux({ react: { dom: ['apps/web/**/*.tsx'], opentui: ['apps/tui/**/*.tsx'] } });
    expect(offRuleFiles(config, 'react/no-unknown-property')).toEqual(['apps/tui/**/*.tsx']);
  });

  test('a non-DOM renderer alone enables react and turns off react/no-unknown-property', () => {
    const config = zyplux({ react: { opentui: ['apps/tui/**'] } });
    expect(hasReactSettings(config)).toBe(true);
    expect(isRuleDisabled(config, 'react/no-unknown-property')).toBe(true);
  });

  test('an empty renderer map is treated as no react', () => {
    expect(hasReactSettings(zyplux({ react: {} }))).toBe(false);
  });
});

describe('withDefaults', () => {
  test('applies shared defaults to every call', () => {
    const tv = zyplux.withDefaults({ react: true, reactVersion: '19.0' });
    expect(reactVersion(tv())).toBe('19.0');
    expect(hasReactSettings(tv())).toBe(true);
  });

  test('a per-call option overrides the shared default', () => {
    const tv = zyplux.withDefaults({ react: true });
    expect(hasReactSettings(tv({ react: false }))).toBe(false);
  });
});
