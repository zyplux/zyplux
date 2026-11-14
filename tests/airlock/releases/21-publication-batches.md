# 21. [Publication batches](test_21_publication_batches.py)

## 21.1 planning isolated publication batches

### 21.1.1 plans one job per release target

### 21.1.2 honors target environments

### 21.1.3 plans action alias repair independently

## 21.2 executing the selected publication batch

### 21.2.1 publishes only the selected npm target and writes its summary

### 21.2.2 honors a single tag plan when several npm targets exist

### 21.2.3 reports a failed npm batch without creating github releases

### 21.2.4 rejects batches that disagree with the checkout

### 21.2.5 publishes a python batch through uv

## 21.3 selecting incomplete releases

### 21.3.1 plans no batches when every release is complete

### 21.3.2 retries a missing artifact whose github release exists

### 21.3.3 selects published artifacts with missing github releases

### 21.3.4 rejects a tag that does not match a configured version

### 21.3.5 plans no batches for a repository with no release targets

### 21.3.6 propagates release lookup failures without emitting a plan
