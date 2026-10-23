# 22. [Custom container artifacts](22-container-artifacts.test.ts)

## 22.1 publishing application-specific container artifacts

### 22.1.1 runs the artifact command with the reviewed version and uploads its manifest before publication

### 22.1.2 rebuilds unfinished releases despite an existing image tag

### 22.1.3 keeps releases unpublished and removes credentials when artifact generation fails

### 22.1.4 preserves a finalized release and its manifest

## 22.2 validating custom artifact declarations

### 22.2.1 rejects asset paths outside the staging directory

### 22.2.2 requires an artifact command for declared assets

### 22.2.3 requires release finalization for artifact commands

### 22.2.4 rejects published container releases with missing declared assets during planning
