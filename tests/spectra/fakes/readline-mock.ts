import { vi } from 'vitest';

vi.mock('node:readline/promises', async importOriginal => {
  const actual = await importOriginal<typeof import('node:readline/promises')>();
  return { ...actual, createInterface: vi.fn(actual.createInterface) };
});
