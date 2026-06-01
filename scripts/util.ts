export const ensure = (condition: boolean, message: string) => {
  if (!condition) {
    throw new Error(message);
  }
};

export const poll = async <T>(probe: () => Promise<T | undefined>, attempts: number, intervalMs: number) => {
  for (let attempt = 0; attempt < attempts; attempt++) {
    const found = await probe();
    if (found !== undefined) {
      return found;
    }
    await Bun.sleep(intervalMs);
  }
  return;
};
