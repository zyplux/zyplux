import { fileURLToPath } from 'node:url';

export const workspaceRoot = fileURLToPath(new URL('../../../', import.meta.url));
