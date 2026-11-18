"""
Project Builder: turns a workflow's generated files into a project workspace, builds and
tests it in an isolated sandbox, and lets the LLM repair failures (bounded attempts).

    structure.py  what the project contains and how to verify each component
    workspace.py  per-user project workspaces (files on disk + metadata, ownership enforced)
    sandbox.py    client for the isolated runner service (never runs code in this process)
    repair.py     LLM diagnosis and validated file fixes
    service.py    the build / repair loop, persisted as ProjectRun rows
"""
