import { runCz } from '@zyplux/cz/cli';
import { createCliRunner } from '@zyplux/spectra/cli-runner';
import { repositoryTest } from '@zyplux/spectra/repository-test';

export const czTest = repositoryTest.extend('cz', () => createCliRunner(runCz));
