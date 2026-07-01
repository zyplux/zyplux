import { runReleaseBumpedTargets } from '@zyplux/cz/commands/release-bumped-targets';
import { loadReleaseTargets, type ReleaseTarget } from '@zyplux/cz/release-targets';
import { fakeShellOutput } from '@zyplux/tests-shell-fixtures';
import { $ } from '@zyplux/util/shell';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@zyplux/util/shell', async importOriginal => {
  const actual = await importOriginal<typeof import('@zyplux/util/shell')>();
  return {
    ...actual,
    $: {
      gh: {
        release: { create: vi.fn(), list: vi.fn() },
        run: { list: vi.fn(), view: vi.fn() },
      },
      git: {
        ...actual.$.git,
        fetch: vi.fn(),
        revParse: vi.fn(),
        status: vi.fn(),
      },
    },
  };
});

const git = vi.mocked($.git, true);
const gh = vi.mocked($.gh, true);

const text = (value: string) => fakeShellOutput(value);
const ok = () => new Response(undefined, { status: 200 });
const notFound = () => new Response(undefined, { status: 404 });

const findTarget = (targets: ReleaseTarget[], label: string) => {
  const target = targets.find(candidate => candidate.label === label);
  if (target === undefined) throw new Error(`${label} target missing from manifest`);
  return target;
};

type StubFetchOptions = {
  ghcrPublished: boolean;
  npmPublished: boolean;
  pypiEverVisible?: boolean;
  pypiPublished: boolean;
};

const stubFetch = ({ ghcrPublished, npmPublished, pypiEverVisible, pypiPublished }: StubFetchOptions) => {
  let pypiCalls = 0;
  vi.stubGlobal('fetch', (input: string | URL) => {
    const url = String(input);
    if (url.includes('/token?')) return Promise.resolve(Response.json({ token: 'gh-token' }));
    if (url.startsWith('https://registry.npmjs.org/')) return Promise.resolve(npmPublished ? ok() : notFound());
    if (url.startsWith('https://ghcr.io/v2/')) return Promise.resolve(ghcrPublished ? ok() : notFound());
    if (url.startsWith('https://pypi.org/')) {
      pypiCalls += 1;
      if (pypiCalls === 1) return Promise.resolve(pypiPublished ? ok() : notFound());
      return Promise.resolve(pypiEverVisible === false ? notFound() : ok());
    }
    return Promise.resolve(notFound());
  });
};

describe('10. Releasing every target whose version was bumped', () => {
  let branchName: string;
  let headSha: string;
  let remoteMainSha: string;
  let workingTreeStatus: string;

  const originalSleep = Bun.sleep;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, 'log').mockReturnValue(undefined);
    vi.spyOn(console, 'warn').mockReturnValue(undefined);
    branchName = 'main';
    headSha = 'sha-head';
    remoteMainSha = 'sha-head';
    workingTreeStatus = '';
    Bun.sleep = () => Promise.resolve();

    git.revParse.mockImplementation((rev, flags) => {
      if (flags?.abbrevRef) return Promise.resolve(text(branchName));
      return Promise.resolve(text(rev === 'HEAD' ? headSha : remoteMainSha));
    });
    git.status.mockImplementation(() => Promise.resolve(text(workingTreeStatus)));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Bun.sleep = originalSleep;
  });

  describe('10.1 validating preconditions', () => {
    it('10.1.1 refuses to run anywhere but main', async () => {
      branchName = 'feat-x';

      await expect(runReleaseBumpedTargets()).rejects.toThrow("releases are cut from main, not 'feat-x'");
      expect(git.status).not.toHaveBeenCalled();
    });

    it('10.1.2 refuses to run with a dirty working tree', async () => {
      workingTreeStatus = ' M some-file.ts';

      await expect(runReleaseBumpedTargets()).rejects.toThrow('working tree is dirty');
      expect(git.fetch).not.toHaveBeenCalled();
    });

    it('10.1.3 refuses to run when local main is behind or ahead of origin/main', async () => {
      remoteMainSha = 'sha-remote-ahead';

      await expect(runReleaseBumpedTargets()).rejects.toThrow('local main and origin/main differ');
    });
  });

  describe('10.2 selecting which targets to release', () => {
    it('10.2.1 skips a target whose version is already published', async () => {
      stubFetch({ ghcrPublished: true, npmPublished: true, pypiPublished: true });
      gh.release.list.mockResolvedValue(text('false'));
      const util = findTarget(await loadReleaseTargets(), '@zyplux/util');
      const utilVersion = await util.readVersion();

      await expect(runReleaseBumpedTargets()).rejects.toThrow('nothing to release; bump a version first');

      expect(console.log).toHaveBeenCalledWith(`Skipping @zyplux/util ${utilVersion} (already published)`);
      expect(gh.release.create).not.toHaveBeenCalled();
    });

    it('10.2.2 skips a target that already has a github release', async () => {
      stubFetch({ ghcrPublished: false, npmPublished: false, pypiPublished: false });
      gh.release.list.mockResolvedValue(text('true'));
      const cerberus = findTarget(await loadReleaseTargets(), 'zyplux-cerberus');
      const cerberusVersion = await cerberus.readVersion();

      await expect(runReleaseBumpedTargets()).rejects.toThrow('nothing to release; bump a version first');

      expect(console.log).toHaveBeenCalledWith(
        `Skipping zyplux-cerberus ${cerberusVersion} (release cerberus-v${cerberusVersion} already exists)`,
      );
      expect(gh.release.create).not.toHaveBeenCalled();
    });

    it('10.2.3 rejects when every target ends up skipped', async () => {
      stubFetch({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      gh.release.list.mockResolvedValue(text('true'));

      await expect(runReleaseBumpedTargets()).rejects.toThrow('nothing to release; bump a version first');

      expect(gh.release.create).not.toHaveBeenCalled();
    });
  });

  describe('10.3 publishing a pending target', () => {
    beforeEach(() => {
      stubFetch({ ghcrPublished: true, npmPublished: true, pypiPublished: false });
      gh.release.list.mockResolvedValue(text('false'));
      gh.run.list.mockImplementation(({ jq } = {}) =>
        Promise.resolve(text(jq === '.[].databaseId' ? '100\n101' : '100\n101\n999')),
      );
    });

    it('10.3.1 cuts a release, watches its workflow to success, and confirms registry visibility', async () => {
      gh.run.view.mockResolvedValueOnce(text('completed\nsuccess'));
      const cerberus = findTarget(await loadReleaseTargets(), 'zyplux-cerberus');
      const cerberusVersion = await cerberus.readVersion();

      await runReleaseBumpedTargets();

      expect(gh.release.create).toHaveBeenCalledWith(`cerberus-v${cerberusVersion}`, {
        generateNotes: true,
        target: 'sha-head',
        title: `cerberus-v${cerberusVersion}`,
      });
      expect(gh.run.view).toHaveBeenCalledWith('999', { jq: '.status, .conclusion', json: 'status,conclusion' });
      expect(console.log).toHaveBeenCalledWith(`Published zyplux-cerberus ${cerberusVersion}`);
    });

    it('10.3.2 rejects when the publish workflow finishes unsuccessfully', async () => {
      gh.run.view.mockResolvedValueOnce(text('completed\nfailure'));

      await expect(runReleaseBumpedTargets()).rejects.toThrow("publish workflow 999 finished with 'failure'");
      expect(console.warn).not.toHaveBeenCalled();
    });

    it('10.3.3 rejects when the publish workflow never starts', async () => {
      gh.run.list.mockImplementation(({ jq } = {}) =>
        Promise.resolve(text(jq === '.[].databaseId' ? '100\n101' : '100\n101')),
      );

      await expect(runReleaseBumpedTargets()).rejects.toThrow('publish workflow did not start; check the Actions tab');
      expect(gh.run.view).not.toHaveBeenCalled();
    });

    it('10.3.4 rejects when the publish workflow never completes', async () => {
      gh.run.view.mockResolvedValue(text('in_progress'));

      await expect(runReleaseBumpedTargets()).rejects.toThrow(
        'publish workflow 999 did not complete within the watch window; check the Actions tab',
      );
    });

    it('10.3.5 warns instead of failing when the registry never shows the new version', async () => {
      stubFetch({ ghcrPublished: true, npmPublished: true, pypiEverVisible: false, pypiPublished: false });
      gh.run.view.mockResolvedValueOnce(text('completed\nsuccess'));
      const cerberus = findTarget(await loadReleaseTargets(), 'zyplux-cerberus');
      const cerberusVersion = await cerberus.readVersion();

      await runReleaseBumpedTargets();

      expect(console.warn).toHaveBeenCalledWith(
        `zyplux-cerberus ${cerberusVersion} published (workflow succeeded) but is not visible on its registry yet — likely propagation lag; it should appear shortly`,
      );
      expect(console.log).not.toHaveBeenCalledWith(expect.stringContaining('Published zyplux-cerberus'));
    });

    it('10.3.6 treats an empty known-run list as no prior runs', async () => {
      gh.run.list.mockImplementation(({ jq } = {}) => Promise.resolve(text(jq === '.[].databaseId' ? '' : '999')));
      gh.run.view.mockResolvedValueOnce(text('completed\nsuccess'));
      const cerberus = findTarget(await loadReleaseTargets(), 'zyplux-cerberus');
      const cerberusVersion = await cerberus.readVersion();

      await runReleaseBumpedTargets();

      expect(console.log).toHaveBeenCalledWith(`Published zyplux-cerberus ${cerberusVersion}`);
    });

    it('10.3.7 rejects when the workflow completes without reporting a conclusion', async () => {
      gh.run.view.mockResolvedValueOnce(text('completed'));

      await expect(runReleaseBumpedTargets()).rejects.toThrow("publish workflow 999 finished with 'unknown'");
    });
  });
});
