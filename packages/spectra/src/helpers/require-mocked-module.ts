import { vi } from 'vitest';

export const requireMockedModule = (subject: unknown, moduleId: string, replaced: string) => {
  if (vi.isMockFunction(subject)) return;
  throw new Error(
    `${moduleId} is not mocked — this project's vitest setupFiles must vi.mock('${moduleId}', …) with ${replaced} wrapped in vi.fn (see @zyplux/spectra README)`,
  );
};
