# Security policy

## Reporting a vulnerability

Please report a vulnerability privately through GitHub's private
vulnerability reporting: open the repository's **Security** tab and choose
**Report a vulnerability**. Do not open a public issue for a security
problem.

## Scope

This repo holds research code, frozen inputs, and synthetic data. It ships
no service. The live runners read an API key from the environment (see
`.env.example`); the repo never stores one. CI runs a secret scan over the
full git history on every push and pull request.
