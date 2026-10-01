---
name: protect-work-repositories
description: Prevent accidental edits, deletion, commits, pushes, remotes, publishing, or destructive Git/GitHub operations on repositories marked as work or protected. Use before any filesystem, Git, GitHub Desktop, or GitHub operation when a workspace contains a protected repository.
---

# Protect work repositories

Apply these rules before touching any repository:

1. Identify the exact repository path and run only read-only checks first.
2. Treat `C:\Users\fimal\OneDrive\Documentos\Leitura Imagem ROM\catalogo_publico` as the personal Yu-Gi-Oh project approved for the current migration.
3. Treat `Grupo-H2-Dados/h2-data-platform` as protected work. Do not edit, delete, rename, commit, reset, checkout, pull, push, publish, change its remote, or change its GitHub visibility.
4. If an operation could affect multiple repositories, stop and narrow it to the approved personal repository.
5. Never use destructive commands against an unresolved path. Do not run `git reset --hard`, `git clean`, recursive deletion, or equivalent cleanup in the protected repository.
6. If GitHub Desktop displays the protected work repository, leave it alone. Use “Add an Existing Repository from your local drive” only for the approved personal project.
7. Before publishing, verify the selected local path, repository name, visibility, and remote. Publish only the approved personal project as private.
8. If the target cannot be proven to be the approved personal repository, ask the user before continuing.
