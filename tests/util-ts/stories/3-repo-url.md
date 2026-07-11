# 3. [Normalizing repo URLs to a canonical form](3-repo-url.test.ts)

## 3.1 normalizing many repo url shapes into a canonical https url

- a git plus https url with a git suffix
- a bare host and path
- an ssh style remote
- a github colon shorthand
- a url with extra path segments
- a non github host url with a git suffix
- a git plus ssh protocol remote

## 3.2 rejecting values that do not name a repository

- an empty string
- a url with no owner and repo path
- a value that is not a url
- an undefined input
