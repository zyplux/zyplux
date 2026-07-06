# 25. [Building a dependency graph of a repo's own source](test_25_graph.py)

## 25.1 connecting files through their imports

### 25.1.1 connects two python files that import each other

### 25.1.2 connects a typescript file to the file it imports via a relative path

### 25.1.3 resolves a workspace package alias import to its entry file

### 25.1.4 resolves a relative import that names a sibling submodule

## 25.2 recording top level symbols

### 25.2.1 adds a contained symbol node for each top level function and class

## 25.3 skipping imports outside the repo

### 25.3.1 adds no node or edge for a third party or standard library import

## 25.4 writing graph output to disk

### 25.4.1 writes graph json to the repo root by default

### 25.4.2 writes output under the directory given via the out option

## 25.5 guarding node ids against the absolute-path bug

### 25.5.1 keeps every node id free of the absolute checkout path

## 25.6 rendering fully in the original graphify CLI

### 25.6.1 stamps each node with graphify compatible source type and community fields

### 25.6.2 marks every contains edge as confidently extracted

## 25.7 resolving absolute import ties deterministically

### 25.7.1 resolves an absolute import tie to the lexicographically first candidate
