import { ensure } from '@zyplux/util/assert';
import { parseJson } from '@zyplux/util/json';
import { poll } from '@zyplux/util/poll';
import { $, readTrimmed } from '@zyplux/util/shell';
import { parse, rcompare } from 'semver';

import type { ActionTarget } from './contracts.ts';

import { ActionReleasesSchema } from './contracts.ts';
import { createGithubRelease } from './github-releases.ts';

const parseRemoteTag = (listing: string, ref: string) => {
  const lines = listing.split('\n');
  const line = lines.find(line => line.endsWith(`\t${ref}^{}`)) ?? lines.find(line => line.endsWith(`\t${ref}`));
  return line?.split('\t', 1)[0] ?? '';
};

const validateActionVersion = (version: string) => {
  const parsed = parse(version);
  ensure(parsed !== null && parsed.prerelease.length === 0, `action version '${version}' must be stable semver`);
  return parsed;
};

const resolveActionAlias = async (
  { major_tag_prefix: majorTagPrefix, repository, tag_prefix: tagPrefix }: ActionTarget,
  version: string,
) => {
  const parsed = validateActionVersion(version);
  const ref = `refs/tags/${majorTagPrefix}${parsed.major}`;
  const previousSha = parseRemoteTag(await readTrimmed($.git.lsRemote('origin', ref)), ref);
  const endpoint = `repos/${repository}/releases?per_page=100`;
  const releases = parseJson(await readTrimmed($`gh api --paginate --slurp ${endpoint}`), ActionReleasesSchema)
    .flat()
    .filter(release => !release.draft && !release.prerelease);
  if (releases.every(release => release.tag_name !== `${tagPrefix}${version}`)) return;
  const latest = releases
    .filter(release => release.tag_name.startsWith(tagPrefix))
    .flatMap(release => {
      const version = parse(release.tag_name.slice(tagPrefix.length));
      return version?.major === parsed.major && version.prerelease.length === 0
        ? { tag: release.tag_name, version }
        : [];
    })
    .toSorted((left, right) => rcompare(left.version, right.version))[0];
  ensure(latest !== undefined, `no published action release for ${ref}`);
  const releaseRef = `refs/tags/${latest.tag}`;
  const commit = parseRemoteTag(await readTrimmed($.git.lsRemote('origin', `${releaseRef}*`)), releaseRef);
  ensure(commit.length > 0, `published action tag ${latest.tag} is missing`);
  return { commit, previousSha, ref, releaseRef };
};

export const isActionPublished = async (target: ActionTarget, version: string) => {
  const alias = await resolveActionAlias(target, version);
  return alias !== undefined && alias.previousSha === alias.commit;
};

export const publishAction = async (target: ActionTarget, version: string, notes: string | undefined) => {
  const tag = `${target.tag_prefix}${version}`;
  validateActionVersion(version);
  if (notes !== undefined && !(await $.gh.release.exists(tag))) {
    await createGithubRelease(tag, notes, await readTrimmed($.git.revParse('HEAD')));
  }
  const alias = await poll(() => resolveActionAlias(target, version), {
    attempts: 12,
    intervalMs: 5000,
    onExpiry: `published GitHub release ${tag} was not visible after waiting; retry publication`,
  });
  if (alias.previousSha === alias.commit) return;
  await $`git fetch --no-tags origin ${alias.releaseRef}`;
  const commit = await readTrimmed($.git.revParse('FETCH_HEAD^{commit}'));
  ensure(commit === alias.commit, `action tag ${alias.releaseRef} changed during publication`);
  await $`git push ${`--force-with-lease=${alias.ref}:${alias.previousSha}`} origin ${`${commit}:${alias.ref}`}`;
};
