# 8. [Requiring ci.yml to run the canonical check sequence](test_8_ci-sequence.py)

## 8.1 scoping the check to repos with a js or python manifest

### 8.1.1 skips repos with no package json or pyproject manifest

## 8.2 requiring a ci workflow file to exist and parse cleanly

### 8.2.1 fails when no ci workflow file exists

### 8.2.2 errors when the ci workflow is not a valid yaml mapping

## 8.3 requiring the python pipeline to run every step in canonical order

### 8.3.1 passes a python ci workflow that runs every required step in order

### 8.3.2 fails when a required python step is missing or does not match its required command

### 8.3.3 fails when the required python steps run out of canonical order

## 8.4 requiring the typescript pipeline to run every step in canonical order within the org container

### 8.4.1 passes a ts ci workflow that runs every required step in order within the org container

### 8.4.2 fails when a required ts step is missing or does not match its required command

### 8.4.3 fails when the required ts steps run out of canonical order

### 8.4.4 fails when the ts job does not run in the org container

### 8.4.5 passes when the container is declared as a mapping with an image key

## 8.5 matching only commands that actually run

### 8.5.1 fails when a required step appears only in a comment
