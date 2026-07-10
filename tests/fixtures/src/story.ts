import { test as base, vi } from 'vitest';

import type { ConsoleCapture } from './console';
import type { FetchFake } from './fetch';
import type { TempDir } from './fs';
import type { PromptFake } from './prompt';
import type { ShellFake } from './shell';

import { createConsoleCapture } from './console';
import { createFetchFake } from './fetch';
import { createTempDir } from './fs';
import { createPromptFake } from './prompt';
import { createShellFake } from './shell';

export type EnvStub = {
  set: (name: string, value: string) => void;
};

export const makeFixture =
  <Subject>(subject: Subject) =>
  async ({}: object, use: (subject: Subject) => Promise<void>) => {
    await use(subject);
  };

export type LibraryFixtures = {
  shell: ShellFake;
  tempDir: TempDir;
};

export const libraryTest = base.extend<LibraryFixtures>({
  shell: async ({}, use) => {
    const shell = createShellFake();
    const restore = shell.install();
    try {
      await use(shell);
    } finally {
      restore();
    }
  },
  tempDir: async ({}, use) => {
    const tempDir = await createTempDir();
    try {
      await use(tempDir);
    } finally {
      await tempDir.remove();
    }
  },
});

export type CliFixtures = {
  env: EnvStub;
  instantSleep: undefined;
  logs: ConsoleCapture;
  network: FetchFake;
  prompt: PromptFake;
};

export const cliTest = libraryTest.extend<CliFixtures>({
  env: async ({}, use) => {
    try {
      await use({
        set: (name, value) => {
          vi.stubEnv(name, value);
        },
      });
    } finally {
      vi.unstubAllEnvs();
    }
  },
  instantSleep: [
    async ({}, use) => {
      const originalSleep = Bun.sleep;
      Bun.sleep = () => Promise.resolve();
      try {
        await use(undefined);
      } finally {
        Bun.sleep = originalSleep;
      }
    },
    { auto: true },
  ],
  logs: [
    async ({}, use) => {
      const logs = createConsoleCapture();
      const restore = logs.install();
      try {
        await use(logs);
      } finally {
        restore();
      }
    },
    { auto: true },
  ],
  network: async ({}, use) => {
    const network = createFetchFake();
    const restore = network.install();
    try {
      await use(network);
    } finally {
      restore();
    }
  },
  prompt: async ({}, use) => {
    const prompt = createPromptFake();
    const restore = prompt.install();
    try {
      await use(prompt);
    } finally {
      restore();
    }
  },
});
