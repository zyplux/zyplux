import type { TSESTree } from '@typescript-eslint/utils';

import { AST_NODE_TYPES, ESLintUtils } from '@typescript-eslint/utils';
import path from 'node:path';
import ts from 'typescript';

import { createRule } from '#create-rule';

type MessageId = 'bindingOutsideSeam' | 'moduleOutsideSeam';
type Options = [{ testApi?: string }];
const testApiNames = new Set([
  'afterAll',
  'afterEach',
  'assert',
  'assertType',
  'beforeAll',
  'beforeEach',
  'bench',
  'describe',
  'expect',
  'expectTypeOf',
  'inject',
  'it',
  'onTestFailed',
  'onTestFinished',
  'suite',
  'test',
  'vi',
  'vitest',
]);
const compilerCache = new Map<string, ts.CompilerOptions>();
const loadCompilerOptions = (file: string) => {
  const config = ts.findConfigFile(path.dirname(file), file => ts.sys.fileExists(file));
  if (config === undefined) return {};
  const cached = compilerCache.get(config);
  if (cached !== undefined) return cached;
  const read = ts.readConfigFile(config, file => ts.sys.readFile(file));
  if (read.error !== undefined) throw new Error(ts.flattenDiagnosticMessageText(read.error.messageText, '\n'));
  const parsed = ts.parseJsonConfigFileContent(read.config, ts.sys, path.dirname(config));
  if (parsed.errors.length > 0)
    throw new Error(ts.flattenDiagnosticMessageText(parsed.errors[0]?.messageText ?? '', '\n'));
  compilerCache.set(config, parsed.options);
  return parsed.options;
};

export const testSeamOnlyImports = createRule<Options, MessageId>({
  create: (context, [{ testApi }]) => {
    const directory = path.dirname(context.filename);
    const domain = path.basename(directory);
    const compiler = loadCompilerOptions(context.filename);
    const resolve = (specifier: string) =>
      ts.resolveModuleName(specifier, context.filename, compiler, ts.sys).resolvedModule?.resolvedFileName;
    const { program } = ESLintUtils.getParserServices(context, true);
    const apiFile = resolve('vitest');
    const apiSource = apiFile === undefined ? undefined : program?.getSourceFile(apiFile);
    const checker = program?.getTypeChecker();
    const apiModule = apiSource === undefined ? undefined : checker?.getSymbolAtLocation(apiSource);
    const allowedNames =
      checker === undefined || apiModule === undefined
        ? testApiNames
        : new Set(checker.getExportsOfModule(apiModule).map(symbol => symbol.name));
    const expected =
      testApi === undefined
        ? path.join(directory, `${domain}.ts`)
        : path.resolve(context.languageOptions.parserOptions.tsconfigRootDir ?? context.cwd, testApi);
    const isSuiteApi = (specifier: string) => {
      if (specifier === 'vitest') return true;
      if (testApi === undefined && specifier === '#fixtures')
        return domain === 'stories' || !directory.split(path.sep).includes('stories');
      const resolved = resolve(specifier);
      const target = specifier.endsWith('.js')
        ? `${specifier.slice(0, -'.js'.length)}.ts`
        : path.extname(specifier) === ''
          ? `${specifier}.ts`
          : specifier;
      return (
        resolved === expected ||
        (resolved === undefined && specifier.startsWith('.') && path.resolve(directory, target) === expected)
      );
    };
    const checkSource = (source: null | TSESTree.StringLiteral) => {
      if (source === null || isSuiteApi(source.value)) return false;
      context.report({ messageId: 'moduleOutsideSeam', node: source });
      return true;
    };
    return {
      ExportAllDeclaration: node => {
        if (!checkSource(node.source)) context.report({ messageId: 'bindingOutsideSeam', node });
      },
      ExportNamedDeclaration: node => {
        if (node.source !== null && !checkSource(node.source))
          context.report({ messageId: 'bindingOutsideSeam', node });
      },
      ImportDeclaration: node => {
        if (checkSource(node.source) || node.importKind === 'type') return;
        for (const specifier of node.specifiers) {
          if (
            specifier.type !== AST_NODE_TYPES.ImportSpecifier ||
            (specifier.importKind !== 'type' &&
              !allowedNames.has(
                specifier.imported.type === AST_NODE_TYPES.Identifier
                  ? specifier.imported.name
                  : specifier.imported.value,
              ))
          )
            context.report({ messageId: 'bindingOutsideSeam', node: specifier });
        }
      },
      ImportExpression: node => {
        context.report({ messageId: 'moduleOutsideSeam', node: node.source });
      },
    };
  },
  defaultOptions: [{}],
  meta: {
    docs: {
      description:
        'Stories import test API bindings from Vitest or their resolved local suite API; fixture types may accompany that API.',
    },
    messages: {
      bindingOutsideSeam:
        'A story imports test API bindings and fixture types from its suite API; helpers reach the story through fixture context.',
      moduleOutsideSeam:
        'A story imports only Vitest or its suite test API; expose this interaction through fixture context.',
    },
    schema: [{ additionalProperties: false, properties: { testApi: { type: 'string' } }, type: 'object' }],
    type: 'problem',
  },
  name: 'test-seam-only-imports',
});
