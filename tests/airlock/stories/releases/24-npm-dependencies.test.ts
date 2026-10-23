import { describe, expect, test } from './releases.ts';

const HTTP_NOT_FOUND = 404;
const HTTP_OK = 200;

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

  test('24.1.2 confines packing failures to their publication jobs', async ({
    airlock,
    consumer,
    planReleases,
    registries,
    repo,
    shell,
  }) => {
    shell.on('pnpm pack', { exitCode: 1, stdout: 'packing failed' }, '');
    const batches = await planReleases();
    expect(shell).not.toHaveRunMatching('pnpm pack');
    const failed = batches.find(batch => batch.tags.includes(consumer.tag));
    const independent = batches.find(batch => batch.tags.includes('independent-v1.2.3'));

    await expect(airlock.run('publish', '--batch', JSON.stringify(failed))).rejects.toThrow('command failed');
    expect(shell).not.toHaveRunMatching('pnpm publish');

    repo.setHeadSha('reviewed-sha');
    shell.on('pnpm publish', () => {
      registries.setPublished({ npmPublished: true });
      return '';
    });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish', '--batch', JSON.stringify(independent));

    expect(shell).toHaveRunMatching('gh release create independent-v1.2.3');
    expect(shell).not.toHaveRunMatching(`gh release create ${consumer.tag}`);
  });

  test.for([
    { override: { private: true }, reason: 'is private' },
    { override: { version: '9.9.9' }, reason: 'configured name and version' },
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
        dependencies: { [consumer.label]: 'workspace:*' },
        name: targets.util.label,
        version: targets.util.version,
      }),
    );

    await expect(airlock.run('publish-npm')).rejects.toThrow('cyclic production workspace dependency');
    expect(shell).not.toHaveRunMatching('pnpm publish');
  });
});

describe('24.3 packed publication dependencies', () => {
  test('24.3.1 publishes a bundle after its packing hook removes private workspace dependencies', async ({
    airlock,
    bundledConsumer,
    expectNpmPublish,
    planReleases,
    registries,
    repo,
    shell,
  }) => {
    const [batch] = await planReleases(bundledConsumer.tag);
    repo.setHeadSha('reviewed-sha');
    shell.on('pnpm publish', () => {
      registries.setPublished({ npmPublished: true });
      return '';
    });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish', '--batch', JSON.stringify(batch));

    await expectNpmPublish(shell, bundledConsumer.dir);
    expect(shell).toHaveRunMatching(`gh release create ${bundledConsumer.tag}`);
  });
});

describe('24.2 waiting for installable dependencies', () => {
  test('24.2.1 waits for dependency metadata and tarball visibility before uploading', async ({
    airlock,
    consumer,
    network,
    planReleases,
    registries,
    repo,
    shell,
  }) => {
    const [batch] = await planReleases(consumer.tag);
    repo.setHeadSha('reviewed-sha');
    let metadataChecks = 0;
    let tarballChecks = 0;
    const expectedMetadataChecks = 3;
    const expectedTarballChecks = 2;
    network.on('https://registry.npmjs.org/%40zyplux%2Futil', () => {
      metadataChecks += 1;
      return Response.json({
        versions: metadataChecks === 1 ? {} : { '1.2.3': { dist: { tarball: 'https://registry.npmjs.org/util.tgz' } } },
      });
    });
    network.on('https://registry.npmjs.org/util.tgz', () => {
      tarballChecks += 1;
      return new Response(undefined, { status: tarballChecks === 1 ? HTTP_NOT_FOUND : HTTP_OK });
    });
    shell.on('pnpm publish', () => {
      expect(tarballChecks).toBe(expectedTarballChecks);
      registries.setPublished({ npmPublished: true });
      return '';
    });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish', '--batch', JSON.stringify(batch));

    expect(shell).toHaveRunMatching(`gh release create ${consumer.tag}`);
    expect(metadataChecks).toBe(expectedMetadataChecks);
  });

  test('24.2.2 blocks a missing dependency’s consumer while allowing an unrelated release', async ({
    airlock,
    consumer,
    planReleases,
    registries,
    repo,
    shell,
  }) => {
    const [dependent] = await planReleases(consumer.tag);
    const [independent] = await planReleases('independent-v1.2.3');

    await expect(airlock.run('publish', '--batch', JSON.stringify(dependent))).rejects.toThrow(
      'npm dependencies did not become available: @zyplux/util@1.2.3',
    );
    expect(shell).not.toHaveRunMatching('pnpm publish');
    repo.setHeadSha('reviewed-sha');
    shell.on('pnpm publish', () => {
      registries.setPublished({ npmPublished: true });
      return '';
    });
    shell.on('gh api graphql', '{"data":{"repository":{"release":null}}}');

    await airlock.run('publish', '--batch', JSON.stringify(independent));

    expect(shell).toHaveRunMatching('gh release create independent-v1.2.3');
    expect(shell).not.toHaveRunMatching(`gh release create ${consumer.tag}`);
  });

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
