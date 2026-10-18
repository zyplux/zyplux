import type { TSESLint } from '@typescript-eslint/utils';

export const collectScopeTree = (root: TSESLint.Scope.Scope): TSESLint.Scope.Scope[] => {
  const scopes: TSESLint.Scope.Scope[] = [];
  const pending = [root];
  while (pending.length > 0) {
    const scope = pending.pop();
    if (!scope) continue;
    scopes.push(scope);
    pending.push(...scope.childScopes);
  }
  return scopes;
};
