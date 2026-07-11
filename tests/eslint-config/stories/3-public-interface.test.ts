// unparametrized
import type { ZypluxConfig as Config } from '#fixtures';

import { describe, expect, test } from '#fixtures';

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

const rendererMap = { dom: ['apps/web/**/*.tsx'], opentui: ['apps/tui/**/*.tsx'] };

describe('3. Configuring eslint through the public zyplux entry point', () => {
  describe('3.1 assembling the base flat config', () => {
    test('3.1.1 enables every rule the zyplux plugin exports', ({ plugin, zyplux }) => {
      const config = zyplux();
      const exported = Object.keys(plugin.rules ?? {});
      const enabled = [
        ...new Set(config.flatMap(entry => Object.keys(entry.rules ?? {}).filter(name => name.startsWith('@zyplux/')))),
      ].map(name => name.replace('@zyplux/', ''));
      expect(exported.length).toBeGreaterThan(0);
      expect(enabled).toContainExactElementsInAnyOrder(exported);
    });

    test('3.1.2 scopes vitest rules to test files', ({ zyplux }) => {
      const config = zyplux();
      const entry = config.find(item => item.plugins !== undefined && 'vitest' in item.plugins);
      expect(entry).toBeDefined();
      expect(entry?.files).toEqual(['**/*.{test,spec}.{ts,tsx}']);
      const vitestRules = Object.keys(entry?.rules ?? {}).filter(name => name.startsWith('vitest/'));
      expect(vitestRules.length).toBeGreaterThan(0);
    });
  });

  describe('3.2 opting into react support', () => {
    test('3.2.1 leaves react disabled by default', ({ zyplux }) => {
      expect(hasReactSettings(zyplux())).toBe(false);
    });

    test('3.2.2 scopes the dom renderer to the default src glob once react is enabled', ({ zyplux }) => {
      expect(reactSettingsFiles(zyplux({ react: true }))).toEqual(['**/src/**/*.{ts,tsx}']);
    });

    test('3.2.3 defaults the react version to detect and forwards a pinned version through', ({ zyplux }) => {
      expect(reactVersion(zyplux({ react: true }))).toBe('detect');
      expect(reactVersion(zyplux({ react: true, reactVersion: '19.0' }))).toBe('19.0');
    });

    test('3.2.4 turns off the no-unknown-property rule for non-dom files only once react is enabled', ({ zyplux }) => {
      expect(isRuleDisabled(zyplux(), 'react/no-unknown-property')).toBe(false);
      expect(isRuleDisabled(zyplux({ nonDomReactFiles: ['apps/tui/**'] }), 'react/no-unknown-property')).toBe(false);
      expect(
        isRuleDisabled(zyplux({ nonDomReactFiles: ['apps/tui/**'], react: true }), 'react/no-unknown-property'),
      ).toBe(true);
    });
  });

  describe('3.3 gating the tanstack route rule', () => {
    test('3.3.1 gates the tanstack route rule behind the tanstack option', ({ zyplux }) => {
      expect(hasRouteRule(zyplux())).toBe(false);
      expect(hasRouteRule(zyplux({ tanstack: true }))).toBe(true);
    });
  });

  describe('3.4 scoping react across multiple renderers', () => {
    test('3.4.1 scopes each renderer in a renderer map to its own file glob', ({ zyplux }) => {
      expect(reactSettingsFiles(zyplux({ react: rendererMap }))).toEqual(['apps/web/**/*.tsx', 'apps/tui/**/*.tsx']);
    });

    test('3.4.2 keeps the no-unknown-property rule for the dom renderer while turning it off for non-dom renderers', ({
      zyplux,
    }) => {
      expect(offRuleFiles(zyplux({ react: rendererMap }), 'react/no-unknown-property')).toEqual(['apps/tui/**/*.tsx']);
    });

    test('3.4.3 enables react and disables no-unknown-property for a renderer map with no dom entry', ({ zyplux }) => {
      const domlessConfig = zyplux({ react: { opentui: ['apps/tui/**'] } });
      expect(hasReactSettings(domlessConfig)).toBe(true);
      expect(isRuleDisabled(domlessConfig, 'react/no-unknown-property')).toBe(true);
    });

    test('3.4.4 treats an empty renderer map or a renderer with no globs as no react', ({ zyplux }) => {
      expect(hasReactSettings(zyplux({ react: {} }))).toBe(false);
      expect(hasReactSettings(zyplux({ react: { dom: [] } }))).toBe(false);
    });
  });

  describe('3.5 sharing defaults across zyplux calls', () => {
    test('3.5.1 applies shared defaults to every call', ({ zyplux }) => {
      const withReactDefaults = zyplux.withDefaults({ react: true, reactVersion: '19.0' });
      expect(reactVersion(withReactDefaults())).toBe('19.0');
      expect(hasReactSettings(withReactDefaults())).toBe(true);
    });

    test('3.5.2 lets a per-call option override a shared default', ({ zyplux }) => {
      const withReactDefaults = zyplux.withDefaults({ react: true });
      expect(hasReactSettings(withReactDefaults({ react: false }))).toBe(false);
    });
  });

  describe('3.6 forwarding caller options into the assembled config', () => {
    test('3.6.1 appends caller ignores to the default global ignores', ({ zyplux }) => {
      const config = zyplux({ ignores: ['generated/**'] });
      const entry = config.find(item => item.ignores?.includes('generated/**'));
      expect(entry).toBeDefined();
      expect(entry?.ignores).toContain('**/dist');
    });

    test('3.6.2 forwards the tsconfig root dir to the typescript parser options', ({ tsconfigRootDirs, zyplux }) => {
      expect(tsconfigRootDirs(zyplux({ tsconfigRootDir: '/repo/root' }))).toEqual(['/repo/root']);
    });
  });
});
