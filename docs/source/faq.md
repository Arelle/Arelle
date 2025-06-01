# FAQ

:::{index} FAQ
:::

## Why Won't Arelle Open?

Running into trouble opening Arelle? It might be a pesky corrupt configuration or
a missing installation file causing the problem. Don't worry! Usually, a [clean install][clean-install]
will set things straight. If that doesn't do the trick, please don't hesitate to
[report a bug][bug-report]. We're here to help, and we'll get to the bottom of it!

[bug-report]: project:index.md#bug-report-or-feature-request
[clean-install]: project:install.md#clean-install

## Why Am I Getting a Validation Error or Warning?

Disagree with an Arelle validation? Open a [change request][change-request] with
a document that triggers the rule and we'll take a look. Some jurisdiction based
validation rules are open to interpretation. In these cases we defer to the community
for consensus.

[change-request]: project:index.md#bug-report-or-feature-request

## Can I Optimize Validation Performance?

By default, Arelle validates the complete DTS (discoverable taxonomy set).
However, you can improve performance in cases where validating the entire
taxonomy set isn't necessary. For instance, when validating reports against a
known-valid taxonomy like US GAAP 2024, you may only need to validate your
report's documents rather than validating the base taxonomy.

To optimize performance in such cases:

- CLI: Use the `--baseTaxonomyValidation=none` option
- GUI: From the `Tools` menu select `Validation` then `Base taxonomy validation`
  and finally select `Don't validate any base files`.

This optimization is particularly useful for service providers who regularly
validate reports against standard taxonomies, reducing validation time while
maintaining the integrity of report-specific validation.

## Why Are Concept Details Missing From the Viewer?

Concept details missing from the Arelle ixbrl-viewer or Edgar Renderer? Check the
Arelle log for download errors. If Arelle can't download the referenced taxonomy
and schemas that define those concept details the viewers will fail to render them.

## Is There a Newer Version of Arelle Available?

New versions of Arelle are typically released multiple times per week. If you're
using one of the [prepackaged distributions][prepackaged-distributions]
you can check for and install updates from the Help menu in the GUI.

[prepackaged-distributions]: project:install.md#prepackaged-distributions
