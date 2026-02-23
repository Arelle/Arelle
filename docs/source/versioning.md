# Versioning

:::{index} Versioning
:::

## Versioning Policy

Arelle follows [Semantic Versioning](https://semver.org/) with a
`MAJOR.MINOR.PATCH` scheme. Versions are derived from git tags via
[setuptools_scm](https://setuptools-scm.readthedocs.io/).

- **MAJOR**: Incremented for breaking changes (incompatible API, CLI, or
  behavioral changes).
- **MINOR**: Incremented for new features and improvements that are backward
  compatible.
- **PATCH**: Incremented for backward-compatible bug fixes.

Users can safely upgrade within the same major version without encountering
breaking changes to core Arelle.

This policy applies to core Arelle. Third-party plugins such as
[EDGAR](https://github.com/Arelle/EDGAR) and
[XULE](https://github.com/xbrlus/xule) maintain their own versioning policies.
Updates to these bundled plugins are always released as minor or patch versions
in the prepackaged builds.

## What Is a Breaking Change?

A breaking change is any modification that requires users to update their
existing workflows, scripts, or integrations. Breaking changes are categorized
by the interface they affect:

- **Python API**: Changes to [arelle.api.Session][python-api] or model object
  interfaces such as renamed methods, removed classes, or changed return types.
- **CLI**: Renamed, removed, or behaviorally changed [command-line flags][cli].
- **GUI**: Removed menu items, dialogs, or workflows.
- **Web Server**: Changed endpoints, request parameters, or response formats.
- **Plugin Hooks**: Removed [hooks][hooks] or arguments from plugin hooks.
- **Python Version Support**: Dropping support for legacy Python versions.
  Arelle supports [Python versions](https://devguide.python.org/versions/)
  that are actively receiving bugfixes and security updates. Running Arelle
  on end-of-life Python versions is not supported or recommended.

## Rollout Lifecycle

Breaking changes follow a phased rollout to give users time to adapt. Not every
phase is feasible for every change. Some changes may skip directly to a later
phase depending on technical constraints.

### Phase 1: Opt-In

The new behavior is introduced alongside the existing behavior. Users must
explicitly enable it (e.g., via a feature flag or configuration setting). This
phase allows early adopters to test the change and provide feedback before it
becomes the default.

### Phase 2: Opt-Out

The new behavior becomes the default. Users who need more time to migrate can
revert to the legacy behavior via a flag or setting. During this phase, the
legacy behavior is still supported but considered deprecated.

### Phase 3: Removal

The legacy code, flags, and deprecated endpoints are permanently removed. After
this phase, only the new behavior is available. This reduces technical debt and
maintenance burden.

### General Timeline

The typical progression for a breaking change is:

1. **Announcement**: The change is communicated through release notes and other
   channels.
2. **Opt-In**: New behavior available for early testing.
3. **Opt-Out**: New behavior becomes the default.
4. **Removal**: Legacy behavior is removed.

The duration of each phase varies based on the scope of the change, user
feedback, and technical constraints. Most breaking changes will target the
following timeline:

- **T-30 days**: Soft launch (opt-in).
- **T-zero**: Hard launch (opt-out).
- **T+60 days**: Cutover (removal of legacy code).

## Communication

Users are notified of breaking changes through the following channels:

- **GitHub Release Notes**: Every release that includes a breaking change will
  document it in the release notes.
- **arelle-users Google Group**: Announcements are posted to the
  [arelle-users](https://groups.google.com/g/arelle-users) group.
- **arelle.org Blog**: Major changes are covered in blog posts on
  [arelle.org](https://arelle.org/arelle/blog/).
- **Direct Outreach**: Key stakeholders and power users may be contacted
  directly for high-impact changes.
- **Mailing List**: Email [support@arelle.org](mailto:support@arelle.org) with
  the subject "Updates" to be added to a mailing list for notifications about
  breaking changes.
- **Monthly Public Standup**: A public standup is held on the third Tuesday of
  every month to discuss recent and upcoming changes to gather feedback. Email
  [support@arelle.org](mailto:support@arelle.org) to receive a Zoom invite.

## Migration Guides

Each breaking change will include migration documentation tailored to the
affected interfaces. These guides provide specific instructions for updating
CLI commands, API calls, GUI workflows, or plugin integrations.

For reference, see:

- [Command Line Reference][cli]
- [Python API Reference][python-api]
- [Plugin Hooks Reference][hooks]

[cli]: project:command_line.md
[python-api]: project:python_api/python_api.md
[hooks]: project:plugins/development/hooks.md
