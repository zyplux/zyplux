import { CliExitError, createCliRunner } from '@zyplux/spectra/cli-runner';
import { createConsoleCapture } from '@zyplux/spectra/console-capture';
import { createFetchFake } from '@zyplux/spectra/fetch-fake';
import { createPromptFake } from '@zyplux/spectra/prompt-fake';
import { createShellFake } from '@zyplux/spectra/shell-fake';
import '@zyplux/spectra/test-matchers';
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
