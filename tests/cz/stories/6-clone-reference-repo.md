# 6. [Shallow-cloning a reference repo](6-clone-reference-repo.test.ts)

## 6.1 building the clone url and destination

1. 6.1.1 builds a github url and destination from an owner/name shorthand
2. 6.1.2 uses a full url as-is and derives the destination from it
3. 6.1.3 derives the destination from a git@ ssh url, stripping the .git suffix
4. 6.1.4 passes a given ref as the branch flag

## 6.2 re-cloning over an existing destination

### 6.2.1 prompts for confirmation and removes the existing destination before cloning
