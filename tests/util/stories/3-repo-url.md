# 3. [Normalizing repo URLs to a canonical form](3_repo-url.test.ts)

## 3.1 normalizing many repo url shapes into a canonical https url

### 3.1.1 strips a leading git plus prefix and a trailing git suffix

### 3.1.2 defaults a bare host and path to an https url

### 3.1.3 converts an ssh style remote to an https url

### 3.1.4 expands a github colon shorthand into a full github url

### 3.1.5 trims extra path segments down to the owner and repo

### 3.1.6 works for a non github host and strips its git suffix

## 3.2 rejecting values that do not name a repository

### 3.2.1 returns undefined for an empty string

### 3.2.2 returns undefined for a url with no owner and repo path

### 3.2.3 returns undefined for a value that is not a url

### 3.2.4 returns undefined for an undefined input
