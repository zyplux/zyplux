# 16. [Linting a repo checkout from the command line](test_16_cli.py)

## 16.1 invoking lint as the default command

### 16.1.1 passes a fully conforming checkout given an explicit path

### 16.1.2 defaults to the current directory when no path argument is given

### 16.1.3 prints one line per bite with its id and outcome

### 16.1.4 appends a bite's measured detail to its line

## 16.2 surfacing check failures end to end

### 16.2.1 fails when the ci workflow file is missing

### 16.2.2 fails on trailing whitespace in the justfile

## 16.3 fixing what can be fixed automatically

### 16.3.1 strips trailing whitespace in place so the rerun then passes

## 16.4 limiting a run to specific named checks

### 16.4.1 runs only the checks named on the command line

### 16.4.2 rejects an unknown check name given on the command line

## 16.5 pointing the linter at an alternate config file

### 16.5.1 uses the recipe requirements from the given config file instead of the bundled defaults

## 16.6 disabling checks per repo via pyproject

### 16.6.1 skips a disabled check and explains why in the output

### 16.6.2 warns and carries on when a pyproject disable list names an unknown check

### 16.6.3 rejects a disable value that is not a list of check ids

## 16.7 listing the available checks

### 16.7.1 lists every registered check by id

## 16.8 printing the installed version

### 16.8.1 prints the cerberus version

## 16.9 guarding the lint command surface against unknown options

### 16.9.1 rejects an option the lint command never defined

## 16.10 isolating a crashing check

### 16.10.1 reports a crashing check as an error instead of aborting the run

## 16.11 rendering a skipped bite distinctly

### 16.11.1 renders a skipped bite with its skip glyph and reason
