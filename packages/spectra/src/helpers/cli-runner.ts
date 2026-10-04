export type CliIo = {
  onExit: (exitCode: number) => never;
  stderr: (line: string) => void;
  stdout: (line: string) => void;
};

export type CliMain = (args: readonly string[], io: CliIo) => Promise<void>;

export type CliRunner = {
  run: (...args: string[]) => Promise<void>;
};

export class CliExitError extends Error {
  readonly exitCode: number;

  constructor(exitCode: number) {
    super(`cli exited with code ${exitCode}`);
    this.name = 'CliExitError';
    this.exitCode = exitCode;
  }
}

export const createCliRunner = (main: CliMain): CliRunner => ({
  run: (...args) =>
    main(args, {
      onExit: exitCode => {
        throw new CliExitError(exitCode);
      },
      stderr: line => {
        console.error(line);
      },
      stdout: line => {
        console.log(line);
      },
    }),
});
