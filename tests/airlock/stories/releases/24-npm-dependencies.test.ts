import { describe, expect, test } from './releases.ts';

const HTTP_NOT_FOUND = 404;
const HTTP_OK = 200;
const HTTP_REQUEST_TIMEOUT = 408;
const HTTP_TOO_MANY_REQUESTS = 429;
const HTTP_UNAVAILABLE = 503;

describe('24.1 isolating npm publication jobs', () => {
  test('24.1.1 plans separate jobs without packing packages or discovering dependencies', async ({
    consumer,
    planReleases,
    shell,
  }) => {
    const batches = await planReleases();

    expect(batches.filter(batch => batch.kind === 'npm').map(batch => batch.tags)).toEqual([
      [consumer.tag],
      ['independent-v1.2.3'],
      ['util-v1.2.3'],
    ]);
    expect(shell).not.toHaveRunMatching(/pnpm pack|pnpm list|tar -xOf/);
  });

  test.for([
    { error: 'command failed', reply: { exitCode: 1, stdout: 'packing failed' } },
    { error: 'npm dependencies did not become available: @zyplux/util@1.2.3', reply: '' },
  ])(
    '24.1.2 confines npm publication failures to their jobs (%j)',
    async ({ error, reply }, { airlock, consumer, planReleases, repo, shell, stageNpmPublication }) => {
      shell.on('pnpm pack', reply, '');
      const batches = await planReleases();
      expect(shell).not.toHaveRunMatching('pnpm pack');
      const failed = batches.find(batch => batch.tags.includes(consumer.tag));
      const independent = batches.find(batch => batch.tags.includes('independent-v1.2.3'));

      await expect(airlock.run('publish', '--batch', JSON.stringify(failed))).rejects.toThrow(error);
      expect(shell).not.toHaveRunMatching('pnpm publish');

      repo.setHeadSha('reviewed-sha');
      stageNpmPublication();

      await airlock.run('publish', '--batch', JSON.stringify(independent));

      expect(shell).toHaveRunMatching('gh release create independent-v1.2.3');
      expect(shell).not.toHaveRunMatching(`gh release create ${consumer.tag}`);
    },
  );

  test.for([
    { override: { private: true }, reason: 'is private' },
    { override: { version: '1.2.4' }, reason: 'configured name and version' },
    { override: { path: '/unconfigured' }, reason: 'declare an npm target' },
  ])(
    '24.1.3 rejects invalid workspace dependencies (%j)',
    async ({ override, reason }, { airlock, consumer, planReleases, shell, targets }) => {
      const [batch] = await planReleases(consumer.tag);
      shell.on(
        'pnpm list',
        JSON.stringify([
          { name: consumer.label, path: consumer.dir, private: false, version: consumer.version },
          {
            name: targets.util.label,
            path: targets.util.dir,
            private: false,
            version: targets.util.version,
            ...override,
          },
        ]),
      );

      await expect(airlock.run('publish', '--batch', JSON.stringify(batch))).rejects.toThrow(reason);
      expect(shell).not.toHaveRunMatching('pnpm publish');
    },
  );

  test('24.1.4 rejects cycles when publishing several npm targets in one command', async ({
    airlock,
    consumer,
    shell,
    targets,
    tempDir,
  }) => {
    await tempDir.write(
      'packages/util/package.json',
      JSON.stringify({
        dependencies: { [consumer.label]: consumer.version },
        name: targets.util.label,
        version: targets.util.version,
      }),
    );

    await expect(airlock.run('publish-npm')).rejects.toThrow('cyclic production workspace dependency');
    expect(shell).not.toHaveRunMatching('pnpm publish');
  });
});

describe('24.3 packed publication dependencies', () => {
  test.for([{ utility: 'npm:@zyplux/util@1.2.3' }, { utility: 'npm:@zyplux/util' }, { '@zyplux/util': 'npm:^1.2.0' }])(
    '24.3.2 waits for the real package behind an npm alias (%j)',
    async (dependencies, { airlock, consumer, planReleases, shell }) => {
      shell.on('tar -xOf', JSON.stringify({ dependencies }));
      const [batch] = await planReleases(consumer.tag);

      await expect(airlock.run('publish', '--batch', JSON.stringify(batch))).rejects.toThrow(
        'npm dependencies did not become available: @zyplux/util@1.2.3',
      );
      expect(shell).not.toHaveRunMatching('pnpm publish');
    },
  );

  test.for([
    { bundleDependencies: ['@zyplux/util'] },
    { bundledDependencies: ['@zyplux/util'] },
    { bundleDependencies: true },
    { bundledDependencies: true },
    { dependencies: { '@zyplux/util': '^9.0.0' } },
    { dependencies: { utility: 'npm:@zyplux/util@^9.0.0' } },
  ])(
    '24.3.3 skips workspace waits for bundled or incompatible dependencies (%j)',
    async (bundling, { airlock, consumer, planReleases, repo, shell, stageNpmPublication }) => {
      shell.on('tar -xOf', JSON.stringify({ dependencies: { '@zyplux/util': '1.2.3' }, ...bundling }));
      const [batch] = await planReleases(consumer.tag);
      repo.setHeadSha('reviewed-sha');
      stageNpmPublication();

      await airlock.run('publish', '--batch', JSON.stringify(batch));

      expect(shell).toHaveRunMatching(`gh release create ${consumer.tag}`);
    },
  );

  test('24.3.1 publishes a bundle after its packing hook removes private workspace dependencies', async ({
    airlock,
    bundledConsumer,
    expectNpmPublish,
    planReleases,
    repo,
    shell,
    stageNpmPublication,
  }) => {
    const [batch] = await planReleases(bundledConsumer.tag);
    repo.setHeadSha('reviewed-sha');
    stageNpmPublication();

    await airlock.run('publish', '--batch', JSON.stringify(batch));

    await expectNpmPublish(shell, bundledConsumer.dir);
    expect(shell).toHaveRunMatching(`gh release create ${bundledConsumer.tag}`);
  });
});

describe('24.2 waiting for installable dependencies', () => {
  test.for([undefined, HTTP_REQUEST_TIMEOUT, HTTP_TOO_MANY_REQUESTS, HTTP_UNAVAILABLE, 'timeout'] as const)(
    '24.2.1 waits for dependency metadata and tarball visibility before uploading (%j)',
    async (failure, { airlock, consumer, network, planReleases, repo, shell, stageNpmPublication }) => {
      const [batch] = await planReleases(consumer.tag);
      repo.setHeadSha('reviewed-sha');
      let metadataChecks = 0;
      let tarballChecks = 0;
      const expectedMetadataChecks = 3;
      const expectedTarballChecks = 2;
      const failRequest = () => {
        if (failure === 'timeout') throw new DOMException('request timed out', 'TimeoutError');
        return new Response(undefined, { status: failure ?? HTTP_NOT_FOUND });
      };
      network.on('https://registry.npmjs.org/%40zyplux%2Futil', () => {
        metadataChecks += 1;
        if (metadataChecks === 1 && failure !== undefined) return failRequest();
        return Response.json({
          versions:
            metadataChecks === 1 ? {} : { '1.2.3': { dist: { tarball: 'https://registry.npmjs.org/util.tgz' } } },
        });
      });
      network.on('https://registry.npmjs.org/util.tgz', () => {
        tarballChecks += 1;
        return tarballChecks === 1 ? failRequest() : new Response(undefined, { status: HTTP_OK });
      });
      stageNpmPublication(() => {
        expect(tarballChecks).toBe(expectedTarballChecks);
      });

      await airlock.run('publish', '--batch', JSON.stringify(batch));

      expect(shell).toHaveRunMatching(`gh release create ${consumer.tag}`);
      expect(metadataChecks).toBe(expectedMetadataChecks);
    },
  );

  test('24.2.3 propagates registry authorization errors before uploading', async ({
    airlock,
    consumer,
    network,
    planReleases,
    shell,
  }) => {
    const [batch] = await planReleases(consumer.tag);
    network.on('https://registry.npmjs.org/%40zyplux%2Futil', () => new Response(undefined, { status: 403 }));

    await expect(airlock.run('publish', '--batch', JSON.stringify(batch))).rejects.toMatchObject({
      response: { status: 403 },
    });
    expect(shell).not.toHaveRunMatching('pnpm publish');
  });
});
