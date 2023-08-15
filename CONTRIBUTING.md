# Contributing

## Pull Request Checklist

Before submitting a pull request, make sure to do the following:

* Ensure you have signed and submitted a [Contributor License Agreement](#contributor-license-agreements).
* Check if your changes are consistent with the [guidelines](#general-guidelines-and-philosophy-for-contribution).
* Changes are consistent with the [Coding Style](#python-coding-style).

## How to become a code contributor

### Contributor License Agreements

We'd love to accept your commits! Before we can take them, we have to jump a
couple of legal hurdles.

Please fill out either the individual or corporate Contributor License
Agreement (CLA).

* If you are an individual writing original source code, then you'll need to
  sign an [individual CLA][cla-individual].
* If you work for a company that wants to allow you to contribute your work,
  then you'll need to sign a [corporate CLA][cla-corporate].

Follow either of the two links above to access the appropriate CLA and
instructions for how to sign and return it. Once you've signed and emailed
the agreement to <Support@Arelle.org> we'll be able to accept your pull requests.

***NOTE***: Only original source code from you and other people that have
signed the CLA can be accepted into the main repository.

[cla-corporate]: https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForEmployees.txt
[cla-individual]: https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForIndividuals.txt

### Setting up an environment

The Arelle implementation is written in Python with the goal to support all stable
versions of Python (not prerelease versions) that are [still receiving security support][python-supported-versions].

1. [Fork][fork-arelle] the Arelle repo
2. Clone your fork: `git clone git@github.com:<your-github-username>/Arelle.git`
3. Install [pyenv][pyenv-install]
4. Install a supported version of Python.
   For example, `pyenv install 3.11.4`
5. Create a virtual env using the Python version you just installed.
   For example, `PYENV_VERSION=3.11.4 pyenv exec python -m venv venv`
6. Activate your environment `source venv/bin/activate`
7. Install dependencies `pip install -r requirements-dev.txt`
8. Verify you can run the app
   1. GUI `python arelleGUI.pyw`
   2. CLI `python arelleCmdLine.py`

[fork-arelle]: https://github.com/Arelle/Arelle/fork
[pyenv-install]: https://github.com/pyenv/pyenv#installation
[python-supported-versions]: https://devguide.python.org/versions/#supported-versions

### Contributing code

If you have improvements or bug fixes for Arelle, send us your pull requests!
For those just getting started, Github has a [how to][using-pull-requests].

Arelle team members will be assigned to review your pull requests. Once the pull
requests are approved and tested an Arelle team member will merge your request.

If you want to contribute, start working through the Arelle codebase, navigate to
the [Github "issues" tab][github-issue-tracker] and start looking through interesting
issues.  If you decide to start on an issue, leave a comment so that other people
know that you're working on it. If you want to help out, but not alone, use the
issue comment thread to coordinate.

[github-issue-tracker]: https://github.com/Arelle/Arelle/issues
[using-pull-requests]: https://help.github.com/articles/using-pull-requests/

### Contribution guidelines and standards

Before submitting your pull request for [review][github-pull-requests], make sure
your changes are consistent with the guidelines and follow the Arelle coding style.

[github-pull-requests]: https://github.com/arelle/arelle/pulls

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

* If necessary, add one or more paragraphs with details, wrapped at 72 characters.
* Use present tense and write in the imperative: “Fix bug”, not “fixed bug” or
  “fixes bug”.
* Separate paragraphs by blank lines.
* Do *not* use special markup (e.g. Markdown). Commit messages are plain text.

#### License

Include a license at the top of new Python files ([example][python-license-example]).

[python-license-example]: https://github.com/Arelle/Arelle/blob/4e88da3b8e8edd368ffb50be01b7daf0324dda4c/arelle/plugin/validate/ESEF/__init__.py#L10

#### Python Coding Style

Stick to the [PEP8 guidelines][pep-0008] and use `mixedCase` for variable and function
names.

[pep-0008]: https://www.python.org/dev/peps/pep-0008/
