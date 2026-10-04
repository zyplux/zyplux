import { pollUntil } from '@zyplux/spectra';
import { test as base } from 'vitest';

export const test = base.extend('pollUntil', () => pollUntil);

export { describe, expect } from 'vitest';
