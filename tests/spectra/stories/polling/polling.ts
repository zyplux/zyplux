import { pollUntil } from '@zyplux/spectra/helpers/poll-until';
import { test as base } from 'vitest';

export const test = base.extend('pollUntil', () => pollUntil);

export { describe, expect } from 'vitest';
