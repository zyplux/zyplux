# 26. [Explaining and querying a built dependency graph](test_26_graph-explore.py)

## 26.1 explaining a single node

### 26.1.1 explains a node found by its exact id

### 26.1.2 explains a node found by a path or label match

### 26.1.3 lists a nodes neighbors with relation and confidence

### 26.1.4 reports no match for an unknown node

### 26.1.5 prefers the file node over a same-file symbol when the query is an exact path

### 26.1.6 marks each connections direction with an arrow

### 26.1.7 announces how many connections were truncated

## 26.2 querying a graph with free text

### 26.2.1 seeds a traversal from the best scoring nodes

### 26.2.2 supports a dfs traversal via the dfs option

### 26.2.3 truncates output to the requested character budget

### 26.2.4 stops expanding through a hub node without excluding the hub itself

### 26.2.5 guarantees a seed for every distinct query term

### 26.2.6 scores rarer terms higher than common terms

## 26.3 requiring a graph to already exist

### 26.3.1 fails with a clear error when graph json does not exist

## 26.4 keeping output machine readable regardless of terminal width

### 26.4.1 never wraps a nodes bracketed metadata onto its own line

## 26.5 scoring a query term against a multi-word label

### 26.5.1 scores a query term as an exact whole-token hit inside a multi-word label
