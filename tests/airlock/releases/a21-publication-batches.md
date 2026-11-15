# a21. [Publication batches](a21_publication_batches_test.py)

## a21.1 planning isolated publication batches

### a21.1.1 plans one job per release target

### a21.1.2 honors target environments

### a21.1.3 plans action alias repair independently

## a21.2 executing the selected publication batch

### a21.2.1 publishes only the selected npm target and writes its summary

### a21.2.2 honors a single tag plan when several npm targets exist

### a21.2.3 reports a failed npm batch without creating github releases

### a21.2.4 rejects batches that disagree with the checkout

### a21.2.5 publishes a python batch through uv

## a21.3 selecting incomplete releases

### a21.3.1 plans no batches when every release is complete

### a21.3.2 retries a missing artifact whose github release exists

### a21.3.3 selects published artifacts with missing github releases

### a21.3.4 rejects a tag that does not match a configured version

### a21.3.5 plans no batches for a repository with no release targets

### a21.3.6 propagates release lookup failures without emitting a plan
