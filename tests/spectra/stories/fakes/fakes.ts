import { createFetchFake } from '@zyplux/spectra/fakes/fetch-fake';
import { createPromptFake } from '@zyplux/spectra/fakes/prompt-fake';
import { createShellFake } from '@zyplux/spectra/fakes/shell-fake';
import { CliExitError, createCliRunner } from '@zyplux/spectra/helpers/cli-runner';
import { createConsoleCapture } from '@zyplux/spectra/reporters/console-capture';
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
