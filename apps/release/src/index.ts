#!/usr/bin/env node
import { runRelease } from './cli.ts';

const SCRIPT_ARGS_START = 2;

try {
  await runRelease(process.argv.slice(SCRIPT_ARGS_START));
} catch (error) {
  console.error(`error: ${error instanceof Error ? error.message : String(error)}`);
  process.exitCode = 1;
}
