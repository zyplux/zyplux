import { createConnection } from 'node:net';

export const openJournalWriter = (identifier: string, socketPath: string) => {
  const writer = createConnection(socketPath);
  let failure: Error | undefined;
  const closed = new Promise<void>(resolve => {
    writer.on('error', error => {
      failure ??= error;
    });
    writer.on('close', () => {
      resolve();
    });
  });
  // sd_journal_stream_fd header: identifier, unit, priority, level prefixes, and three forwarding flags.
  writer.write(`${identifier}\n\n6\n1\n0\n0\n0\n`);
  return {
    close: async () => {
      writer.end();
      await closed;
      if (failure) console.error(`recording ${identifier} to the journal failed`, failure);
    },
    write: (lines: readonly string[]) => {
      if (lines.length > 0 && !writer.destroyed) writer.write(`${lines.join('\n')}\n`);
    },
  };
};
