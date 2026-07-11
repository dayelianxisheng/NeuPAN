# Unified project-root migration

## Authorization and scope

The user authorized migration of all existing SGCF-NRMP stage 01/02 files into
the single project root `sgcf_nrmp_project/`. No NeuPAN protected path was part
of the migration.

## Mapping

```text
sgcf_nrmp/           -> sgcf_nrmp_project/core/
sgcf_nrmp_docs/      -> sgcf_nrmp_project/docs/
sgcf_nrmp_artifacts/ -> sgcf_nrmp_project/artifacts/
sgcf_nrmp_tools/     -> sgcf_nrmp_project/tools/
COPYING_NOTICE.md    -> sgcf_nrmp_project/COPYING_NOTICE.md
docs/codex/          -> sgcf_nrmp_project/docs/codex/
```

Executable defaults, test commands, documentation links and artifact locations
were updated. Historical reports retain their measured results and explicitly
record that their paths were migrated after acceptance.

## Rule going forward

No new root-level `sgcf_nrmp`, `sgcf_nrmp_docs`, `sgcf_nrmp_artifacts`,
`sgcf_nrmp_tools`, `sgcf_nrmp_ros2`, `sgcf_nrmp_gazebo` or `sgcf_nrmp_deploy`
directory is allowed. The Python import package remains `sgcf_nrmp`.
