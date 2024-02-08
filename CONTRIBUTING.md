# Contributing

## Pull Request Checklist

We'd love for you to contribute to Arelle, but before you hit that "submit" button,
make sure to:

* Sign and submit a [Contributor License Agreement](#contributor-license-agreements).
  It's a legal thing; we'll explain below.
* See if your changes play nice with our [guidelines](#general-guidelines-and-philosophy-for-contributions).
* Make sure your code aligns with our [Coding Style](#python-coding-style).

## How To Become a Code Contributor

### Contributor License Agreements

We'd love to accept your commits! But first, some legal bits:

* If you are an individual writing original source code, sign an [individual CLA][cla-individual].
* If you work for a company that wants to allow you to contribute your work, sign
  a [corporate CLA][cla-corporate].

Follow the links to get everything sorted. Email the signed form to <Support@arelle.org>,
and we'll be ready to take your pull requests.

***NOTE***: Only original source code from people who have signed the CLA can be
accepted into the main repository.

[cla-corporate]: https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForEmployees.txt
[cla-individual]: https://arelle.org/arelle/wp-content/uploads/2010/11/ContributorLicenseForIndividuals.txt

### Setting Up Your Environment

You'll be working with Python. The Arelle implementation aims to support all stable
versions of Python (not prerelease versions) that are [still receiving security support][python-supported-versions].
Here's how to set up your environment:

<details>

  <summary>  Fork the Arelle repository  </summary>
<br>


  [Click here](https://github.com/Arelle/Arelle/fork) to fork the Arelle repository. 

</details>

<details>

  <summary> Clone your fork </summary>
<br>


  ```
  git clone https://github.com/<your-github-username>/Arelle.git
  ```



</details>

<details>
<summary> Create the Pyenv Virtual environment </summary>
<br>


  1. Install [pyenv][pyenv-install]
  2. Install a supported version of Python.
    For example, 
    
    pyenv install 3.12.2

  3. Create a virtual env using the Python version you just installed.
    For example, 

    PYENV_VERSION=3.12.2 pyenv exec python -m venv venv
  4. Activate your environment: 
    
    source venv/bin/activate
    
    

</details>

<details>

  <summary> Install dependencies </summary>
<br>


  ```
  pip install -r requirements-dev.txt
  ```

</details>
<details>

<summary> Verify you can run the app </summary>
<br>

  1. GUI: 
  ``` 
  python arelleGUI.pyw 
  ```

  2. CLI: 
  ```
  python arelleCmdLine.py
  ```
</details>

[fork-arelle]: https://github.com/Arelle/Arelle/fork
[pyenv-install]: https://github.com/pyenv/pyenv#installation
[python-supported-versions]: https://devguide.python.org/versions/#supported-versions

</details>

### Contributing Code

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

### Contribution Guidelines and Standards

Before submitting your pull request for [review][github-pull-requests], make sure
your changes are consistent with the guidelines and follow the Arelle coding style.

[github-pull-requests]: https://github.com/arelle/arelle/pulls

#### General Guidelines and Philosophy for Contributions

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

#### How To Craft a Good Commit Message

* Write one or more paragraphs with details, wrapped at 72 characters.
* Write in the present tense: "Fix bug" not "Fixed bug".
* Separate paragraphs with a single blank line.
* No markup, please! Commit messages should be plain text.

#### Include a License

Include a license at the top of new Python files ([example][python-license-example]).

[python-license-example]: https://github.com/Arelle/Arelle/blob/4e88da3b8e8edd368ffb50be01b7daf0324dda4c/arelle/plugin/validate/ESEF/__init__.py#L10

#### Python Coding Style

Stick to the [PEP8 guidelines][pep-0008] and use `mixedCase` for variable and function
names.

[pep-0008]: https://www.python.org/dev/peps/pep-0008/
