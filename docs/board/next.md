# Next

- extract idempotence logic from cooks into chef. Cooks need to be minimalist - only know how to check presence/installed version(s), only know how to upgrade and how to show available (latest) version(s). The logic should be handled by the chef. Behavior should not change from the current, just the logic moves to the chef.
- file_cook to write files as several bash cooks may be simpler by doing file write only
- chef to run everything in parallel, where possible, and respecting depends_on
- convert configure_apps and configure_gpu into cooks - create new cooks if needed or convert into one or many existing cooks
- print report table in the end showing current and latest version and what has been installed or upgraded or unchanged
- convert the chef into a cli with typer
- support chef view only mode flag (pick standard name) displaying the currntly installed and latest versions as a table
