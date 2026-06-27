import * as z from 'zod';

export const LooseRecordSchema = z.record(z.string(), z.unknown());
export const StringRecordSchema = z.record(z.string(), z.string());
export const StringArraySchema = z.array(z.string());
export const UnknownArraySchema = z.array(z.unknown());
export const UnknownArrayRecordSchema = z.record(z.string(), UnknownArraySchema);

export const IdSchema = z.object({ id: z.string() });
export const VersionKeySchema = z.object({ version: z.string() });
