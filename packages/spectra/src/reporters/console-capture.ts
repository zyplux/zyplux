export type ConsoleCapture = {
  errorLines: string[];
  install: () => () => void;
  logLines: string[];
  warnLines: string[];
};

const renderLine = (parts: unknown[]) => parts.map(String).join(' ');

export const createConsoleCapture = (): ConsoleCapture => {
  const errorLines: string[] = [];
  const logLines: string[] = [];
  const warnLines: string[] = [];

  return {
    errorLines,
    install: () => {
      const original = { error: console.error, log: console.log, warn: console.warn };
      console.error = (...parts: unknown[]) => {
        errorLines.push(renderLine(parts));
      };
      console.log = (...parts: unknown[]) => {
        logLines.push(renderLine(parts));
      };
      console.warn = (...parts: unknown[]) => {
        warnLines.push(renderLine(parts));
      };
      return () => {
        console.error = original.error;
        console.log = original.log;
        console.warn = original.warn;
      };
    },
    logLines,
    warnLines,
  };
};
