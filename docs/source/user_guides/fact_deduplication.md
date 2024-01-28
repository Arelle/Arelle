# Fact Deduplication

:::{index} Fact Deduplication
:::

Duplicate facts criteria are defined by [the OIM specification][oim].
Arelle detects duplicate facts by first grouping facts into *duplicate sets*, as defined [here][oim-duplicates].
From there, Arelle can detect if any, all, or none of the facts contained in each set are of the various *types* of duplicates defined by OIM: inconsistent, consistent, and complete.
Using this information, Arelle can trigger warnings or remove duplicate facts as described below.

## Duplicate Fact Validation
### CLI
To detect and trigger warnings when duplicate facts are encountered, use `--validateDuplicateFacts` in conjunction with `--validate`.
The valid choices to pass with `--validateDuplicateFacts` are:

| Argument       | Duplicate set fires warning...                    |
|----------------|---------------------------------------------------|
| `none`         | Never                                             |
| `inconsistent` | If any facts in set are NOT consistent duplicates |
| `consistent`   | If any facts in set are consistent duplicates     |
| `incomplete`   | If any facts in set are NOT complete duplicates   |
| `complete`     | If any facts in set are complete duplicates       |
| `all`          | Always                                            |


Example:
```bash
python arelleCmdLine.py --file instance.xbrl --validate --validateDuplicateFacts inconsistent
```

### GUI
This feature is also available in the GUI by selecting an option under *Tools > Validation > Warn on duplicate facts...*

## Deduplicating Traditional XBRL Instance
To save a copy of an instance document with duplicate facts removed, use `--saveDeduplicatedInstance`.
Optionally, provide `--deduplicateFacts` with an argument to specify the logic to use for deduplication.
The default is `complete`.

| Argument           | Deduplication result                                                                                   |
|--------------------|--------------------------------------------------------------------------------------------------------|
| `complete`         | One fact for each complete subset                                                                      |
| `consistent-pairs` | After `complete` deduplication, excludes any fact that has a consistent duplicate of higher precision  |
| `consistent-sets`  | If the set is fully consistent, only the highest precision fact is kept. Otherwise, same as `complete` |


Example:
```bash
python arelleCmdLine.py --file instance.xbrl --deduplicateFacts consistent-pairs --saveDeduplicatedInstance output.xbrl
```

[oim]: https://www.xbrl.org/Specification/oim/REC-2021-10-13+errata-2023-04-19/oim-REC-2021-10-13+corrected-errata-2023-04-19.html
[oim-duplicates]: https://www.xbrl.org/Specification/oim/REC-2021-10-13+errata-2023-04-19/oim-REC-2021-10-13+corrected-errata-2023-04-19.html#sec-duplicate-facts
