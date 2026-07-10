import { vi } from 'vitest';

export type PromptFake = {
  install: () => () => void;
  messages: string[];
};

export const createPromptFake = (): PromptFake => {
  const messages: string[] = [];

  return {
    install: () => {
      const original = globalThis.prompt;
      vi.stubGlobal('prompt', (message?: string) => {
        messages.push(message ?? '');
        return '';
      });
      return () => {
        vi.stubGlobal('prompt', original);
      };
    },
    messages,
  };
};
