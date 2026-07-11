# 3. [Normalizing repo URLs to a canonical form](3-repo-url.test.ts)

## 3.1 normalizing many repo url shapes into a canonical https url

1. 3.1.1 a git plus https url with a git suffix
2. 3.1.2 a bare host and path
3. 3.1.3 an ssh style remote
4. 3.1.4 a github colon shorthand
5. 3.1.5 a url with extra path segments
6. 3.1.6 a non github host url with a git suffix
7. 3.1.7 a git plus ssh protocol remote

## 3.2 rejecting values that do not name a repository

1. 3.2.1 an empty string
2. 3.2.2 a url with no owner and repo path
3. 3.2.3 a value that is not a url
4. 3.2.4 an undefined input
