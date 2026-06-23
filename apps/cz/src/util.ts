export const ensure: (isMet: boolean, message: string) => asserts isMet = (isMet, message) => {
  if (!isMet) {
    throw new Error(message);
  }
};

type CommandOutput = { text: () => string };

export const readTrimmed = async (command: Promise<CommandOutput>) => {
  const output = await command;
  return output.text().trim();
};

type PollOptions = { attempts: number; intervalMs: number };

export const poll = async <T>(probe: () => Promise<T | undefined>, { attempts, intervalMs }: PollOptions) => {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const found = await probe();
    if (found !== undefined) {
      return found;
    }
    await Bun.sleep(intervalMs);
  }
  return;
};
