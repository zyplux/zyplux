from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, TypeAdapter

if TYPE_CHECKING:
    from pathlib import Path

type ReleaseKind = Literal["npm", "pypi", "ghcr", "action"]
type Nonempty = Annotated[str, Field(min_length=1)]
type Digest = Annotated[str, Field(pattern=r"^sha256:[\da-f]{64}$")]


class JsonVersion(BaseModel):
    file: str
    json_path: str = Field(alias="json")


class RegexVersion(BaseModel):
    file: str
    regex: str


class TargetBase(BaseModel):
    label: str = ""
    tag_prefix: str = ""
    environment: Nonempty | None = None
    surface: list[str]
    version: JsonVersion | RegexVersion


class PackageSpec(TargetBase):
    kind: Literal["npm", "pypi"]


class ContainerSpec(TargetBase):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["ghcr"]
    dockerfile: Nonempty | None = None
    build_context: Nonempty | None = None


class ActionSpec(TargetBase):
    kind: Literal["action"]
    repository: Annotated[str, Field(pattern=r"^[\w.-]+/[\w.-]+$")]


type TargetSpec = Annotated[PackageSpec | ContainerSpec | ActionSpec, Field(discriminator="kind")]
TARGET_SPEC = TypeAdapter(TargetSpec)
STRING = TypeAdapter(str)
VERSION_OBJECT = TypeAdapter(dict[str, object])
DIGEST = TypeAdapter(Digest)


@dataclass(frozen=True)
class ReleaseTarget:
    spec: TargetSpec
    version: str
    directory: Path
    build_context: Path | None = None
    dockerfile: Path | None = None

    @property
    def tag(self) -> str:
        return f"{self.spec.tag_prefix}{self.version}"

    @property
    def environment(self) -> str:
        return self.spec.environment or ("actions" if self.spec.kind == "action" else self.spec.kind)


class ReleaseBatch(BaseModel):
    environment: Nonempty
    id: Nonempty
    kind: ReleaseKind
    runner: Literal["ubuntu-latest"]
    tags: Annotated[list[str], Field(min_length=1, max_length=1)]


class PythonTracking(BaseModel):
    name: str
    version: str
    private: Literal[True]


class NpmPackage(BaseModel):
    dependencies: dict[str, str] = Field(default_factory=dict)
    optional_dependencies: dict[str, str] = Field(default_factory=dict, alias="optionalDependencies")
    scripts: dict[str, str] = Field(default_factory=dict)
    publish_config: dict[str, object] = Field(default_factory=dict, alias="publishConfig")
    bundled_dependencies: bool | list[str] | None = Field(default=None, alias="bundledDependencies")
    bundle_dependencies: bool | list[str] | None = Field(default=None, alias="bundleDependencies")


class NpmArchive(NpmPackage):
    name: str
    version: str


class WorkspacePackage(BaseModel):
    name: str | None = None
    version: str | None = None
    private: bool
    path: str


WORKSPACE_PACKAGES = TypeAdapter(list[WorkspacePackage])


class NpmVersions(BaseModel):
    versions: dict[str, object]


class Tarball(BaseModel):
    tarball: HttpUrl


class NpmArtifact(BaseModel):
    dist: Tarball


class NpmTags(BaseModel):
    latest: str


class NpmLatest(BaseModel):
    tags: NpmTags = Field(alias="dist-tags")


class PypiFile(BaseModel):
    packagetype: str


class PypiFiles(BaseModel):
    urls: list[PypiFile]


class PypiInfo(BaseModel):
    version: str


class PypiLatest(BaseModel):
    info: PypiInfo


class GithubUser(BaseModel):
    login: Nonempty


class GhcrToken(BaseModel):
    token: str


class GhcrTags(BaseModel):
    tags: list[str] | None


class ContainerManifest(BaseModel):
    image: str
    version: str


class ActionRelease(BaseModel):
    draft: bool
    prerelease: bool
    tag_name: str


ACTION_RELEASES = TypeAdapter(list[list[ActionRelease]])


class ReleaseAsset(BaseModel):
    name: str


class ReleaseAssets(BaseModel):
    nodes: list[ReleaseAsset]


class GithubRelease(BaseModel):
    id: str | None = None
    is_draft: bool = Field(default=False, alias="isDraft")
    release_assets: ReleaseAssets = Field(default_factory=lambda: ReleaseAssets(nodes=[]), alias="releaseAssets")


class GithubRepository(BaseModel):
    release: GithubRelease | None


class GithubData(BaseModel):
    repository: GithubRepository


class GithubLookup(BaseModel):
    data: GithubData
