<div align="center">
  <img src="http://arelle.org/arelle/wp-content/themes/platform/images/logo-platform.png">
</div>

# Contributing guidelines

## Reporting issues

Please report issues to the [issue tracker](https://github.com/arelle/arelle/issues).

* Check that the issue has not already been reported.
* Check that the issue has not already been fixed in the latest code.
* Be clear and precise (do not prose, but name functions and commands exactly).
* Include the version of Arelle.


## Pull Request Checklist

Before sending your pull requests, make sure you do the following:

*   Read the [contributing guidelines](CONTRIBUTING.md).
*   Ensure you have signed the [Contributor License Agreement (CLA)](#conttributor-license-agreements).
*   Check if your changes are consistent with the [guidelines](#general-guidelines-and-philosophy-for-contribution).
*   Changes are consistent with the [Coding Style](#python-coding-style).


## How to become a contributor and submit your own code


### Contributor License Agreements

We'd love to accept your commits! Before we can take them, we have to jump a couple of legal hurdles.

Please fill out either the individual or corporate Contributor License Agreement (CLA).

* If you are an individual writing original source code, then you'll need to sign an [individual CLA](https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForIndividuals.txt).
* If you work for a company that wants to allow you to contribute your work, then you'll need to sign a [corporate CLA](https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForEmployees.txt).

Follow either of the two links above to access the appropriate CLA and instructions for how to sign and
return it. Once we receive it, we'll be able to accept your pull requests.

***NOTE***: Only original source code from you and other people that have signed the CLA can be accepted into the main repository.

### Setting up an environment
1. Install [pyenv](https://github.com/pyenv/pyenv#installation)
2. Install a [supported version of Python](https://github.com/Arelle/Arelle/blob/master/INSTALLATION.md). For example, `pyenv install 3.9.9`
3. Create a virtual env using the minimum python version. For example, `PYENV_VERSION=3.9.9 pyenv exec python -m venv venv`
4. Activate your environment `source venv/bin/activate`
5. Install dependencies `pip install -r requirements-dev.txt`
6. Verify you can run the app
   1. GUI `python arelleGUI.pyw`
   2. CLI `python arelleCmdLine.py`

### Contributing code

If you have improvements or bug fixes for Arelle, send us your pull requests! For those
just getting started, Github has a [how to](https://help.github.com/articles/using-pull-requests/).

Arelle team members will be assigned to review your pull requests. Once the
pull requests are approved and tested an Arelle team member will merge your request.

If you want to contribute, start working through the Arelle codebase,
navigate to the
[Github "issues" tab](https://github.com/arelle/arelle/issues) and start
looking through interesting issues. If you decide to start on an issue, leave a
comment so that other people know that you're working on it. If you want to help
out, but not alone, use the issue comment thread to coordinate.


### Contribution guidelines and standards

Before sending your pull request for [review](https://github.com/arelle/arelle/pulls),
make sure your changes are consistent with the guidelines and follow the
Arelle coding style.


#### General guidelines and philosophy for contribution

* When you contribute a bug fix to Arelle, make sure to fully document the bug and
  how it was fixed in the PR. Additionally, supply possible ways that the fix could
  be manually tested. This will greatly improve the testing and time required to
  merge the fix.
* When you contribute a new feature or plugin to Arelle, make sure to include
  documentation in the code with a markdown file on how to use the feature/plugin
  and what benefit it provides.
* When you contribute a new feature or plugin to Arelle, make sure to point at the
  documentation in the PR and supply ways the new feature/plugin could be manually
  tested. This will make testing significantly easier for the Arelle team and reduce
  the time required to merge the feature.
* When you contribute a new feature or plugin to Arelle, the maintenance burden
  is (by default) transferred to the Arelle team. This means that the benefit
  of the contribution must be compared against the cost of maintaining the feature.


#### Commit messages

Write commit messages according to the following guidance:

* If necessary, add one or more paragraphs with details, wrapped at 72
  characters.
* Use present tense and write in the imperative: “Fix bug”, not “fixed bug” or
  “fixes bug”.
* Separate paragraphs by blank lines.
* Do *not* use special markup (e.g. Markdown). Commit messages are plain text.


#### License

Include a license at the top of new files.

* [Python license example](https://github.com/Arelle/Arelle/blob/a0a6fbc0bc901262dbab0dd6aad3b45313e5ab8e/arelle/plugin/validate/ESEF/__init__.py#L12-L13)


#### Python coding style

Changes to Arelle Python code should conform to [PEP8 guidelines](https://www.python.org/dev/peps/pep-0008/)