import {
  CliExitError,
  createCliRunner,
  createConsoleCapture,
  createFetchFake,
  createPromptFake,
  createShellFake,
} from '@zyplux/spectra';
import { createInterface } from 'node:readline/promises';
import { test as base } from 'vitest';

const createCliExitError = (exitCode: number) => new CliExitError(exitCode);

const askQuestion = async (message: string) => {
  const prompt = createInterface({ input: process.stdin, output: process.stdout });
  try {
    return await prompt.question(message);
  } finally {
    prompt.close();
  }
};

export const test = base
  .extend('askQuestion', () => askQuestion)
  .extend('createCliExitError', () => createCliExitError)
  .extend('createCliRunner', () => createCliRunner)
  .extend('createConsoleCapture', () => createConsoleCapture)
  .extend('createFetchFake', () => createFetchFake)
  .extend('createPromptFake', () => createPromptFake)
  .extend('createShellFake', () => createShellFake);

export { describe, expect } from 'vitest';
