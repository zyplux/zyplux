# Workspace Dependency Graph

*Which workspace projects depend on each other?*

```mermaid
---
config:
  theme: dark
  layout: elk
---
flowchart LR
    subgraph workspaces
        subgraph group_0["apps"]
            ws_1["zyplux-setup-pm"]
            ws_2["zyplux-airlock"]
            ws_3["zyplux-cerberus"]
            ws_4["clipy"]
            ws_5["cz"]
            ws_6["token-stats"]
            ws_7["totchef"]
        end
        subgraph group_1["packages"]
            ws_8["eslint-config"]
            ws_9["spectra"]
            ws_10["tsconfig"]
            ws_11["util"]
            ws_12["zyplux-util"]
        end
        subgraph group_2["root"]
            ws_0["zyplux"]
        end
    end
    ws_0 ws_0__ws_8@--> ws_8
    ws_0 ws_0__ws_9@--> ws_9
    ws_0 ws_0__ws_10@--> ws_10
    ws_3 ws_3__ws_2@--> ws_2
    classDef ws_3_edges stroke:#e467c9,stroke-width:2px
    class ws_3__ws_2 ws_3_edges
    ws_5 ws_5__ws_10@--> ws_10
    ws_5 ws_5__ws_11@--> ws_11
    classDef ws_5_edges stroke:#e4db67,stroke-width:2px
    class ws_5__ws_10,ws_5__ws_11 ws_5_edges
    ws_8 ws_8__ws_10@--> ws_10
    ws_8 ws_8__ws_11@--> ws_11
    ws_9 ws_9__ws_10@--> ws_10
    ws_11 ws_11__ws_10@--> ws_10
    classDef foundation fill:#2b2b2b,stroke:#888,stroke-dasharray:5 5
    style workspaces fill:transparent,stroke:none
```

Solid arrows are declared workspace dependencies; dashed arrows have only type imports in TypeScript source.

Generate with `uv run cerberus workspace-graph`.
