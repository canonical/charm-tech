# OP058 — Distributing Charm Libraries as Python Packages

| Field | Value |
| --- | --- |
| Status | Rejected |
| Type | Informational |
| Created | 2023-03-09 |

## Abstract

As the charming ecosystem matures, charm-libs have proven themselves to be a useful tool for sharing code in some contexts, such as for providing relation classes like DatabaseRequires, but limiting in others, such as sharing non-trivial code that has dependencies of its own. This spec outlines recommendations for structuring and sharing such library code as standard Python packages.

## Rationale

Historically, charmcraft fetch style libs have been the only endorsed mechanism for sharing code between charms, but the limitations of this format have introduced difficulties, as many of the respondents to Charm Tech's Charming Surveys have noted. Dependency management is particularly troublesome due to [PYDEPS](https://docs.google.com/document/d/11JsKoxtIdFGy5LK9OYSMfMCR87hPpNt1tT8avoTy6RU/edit?tab=t.0#heading=h.fg9ujlrx1n8t) not being well supported by tooling. This has led to some teams beginning to consider distributing their shared code as standard Python packages, which have well established dependency resolution mechanisms. Charm Tech believes that Python packages are an excellent way to distribute shared charm code. To maximise the number of charms that can benefit from such shared code, this specification suggests some best practices.

## Recommendations

#### Namespace and naming

Charmcraft libs are imported via the 'charms' namespace. This makes sense because each is associated with, and organised under, a charm. For charm libraries distributed as Python packages, which are not associated with a charm in the same way, we recommend creating a namespace package using the 'charmlibs' namespace. The package name should be 'charmlibs-$libname', imported as 'from charmlibs import $libname'.

If you have a dedicated repository for the charmlib, we recommend naming it 'charmlibs-$libname' as well. For repositories containing several libraries, consider '$teamname-charmlibs'. The individual packages should still follow the naming and namespace recommendations. Of course these library repository naming recommendations need not apply to other cases like a library developed in the repository for a charm, or a monorepo developing multiple charms.

Note on namespace packages: All this means is that the actual package is nested under an empty directory named charmlibs. Your file structure might look like '$repositoryname/src/charmlibs/$libname/__init__.py'. There is no need to install the actual package named charmlibs. This exists on PyPI solely to reserve the package name as a namespace for charm libraries and to aid charm library discoverability.

There are some charmer developed Python packages that use the 'ops' or 'charms' namespaces instead. We don't recommend using the 'ops' namespace for your own packages. It will be easier for charmers to follow your code if this namespace is reserved for the ops package. Likewise, the 'charms' namespace is best left for the charmcraft fetch style libs. Charm Tech recommends using the 'charmlibs' namespace when releasing charm libraries as Python packages.

#### When to use a Python package

When should you use a Python package for your charm library, vs distribution via charmcraft fetch libs? In short, if your library relies on any dependencies outside the Python standard library and the 'ops' package, you should definitely use a Python package.

If a charm library seems like it will be difficult to manage as a single file, this is another strong sign that it should be a Python package.

For any new libraries that are not logically associated with a single charm, including those that are used by both the charmed machine and Kubernetes versions of a piece of software, consider if using a Python package will make your life easier. This is especially likely to be the case if you are sharing multiple modules between machine and Kubernetes versions of a charm, where the individual modules would not be separate Python packages - in this case a single Python package will be easier to manage than multiple (perhaps interdependent) charmcraft libs.

The main case where charmcraft libs are likely to be a good choice is for relations. In this case, the library is associated with a specific charm, it is likely to be simple enough for a single file (as a lot of logic likely lives in the related charms), and there is existing infrastructure and documentation supporting this pattern.

#### Distribution

##### PyPI

Use trusted publishing to publish directly from your github repository. You can set up trusted publishing like so on PyPI, and by using these github workflows in your repo ... (**TODO)**

Remember that once you have trusted publishing set up, anyone who can trigger that workflow can publish the package, so make sure you assign permissions on your repository accordingly (**TODO:** how?).  The team manager and another trusted team member should be the package owners on PyPI, using their Canonical email addresses. Also be sure to claim the package on test.pypi.org - your test release workflow can publish to test PyPI.

A major benefit of publishing on PyPI is that users of your library can specify version ranges in their dependencies. Therefore, if you're going to publish on PyPI, we highly recommend that you use semantic versioning for your library.

A non-dev/alpha/beta/etc qualified 1.x release to PyPI signifies that your library is ready for public consumption. You should also communicate this through the ["Development Status" Trove classifier](https://pypi.org/classifiers/) in your pyproject.toml (or whatever configuration file you're using - but pyproject.toml is standard now). *This is a good opportunity to ask Charm Tech for review so that we can update your library in the listing.*

##### GitHub

You can get started by distributing your library as a Python package with very little friction using GitHub. This is good for prototyping, or when first transitioning from a charm-lib to a Python package, and may be a good fit for libraries that are intended for team-internal use. Once you're done prototyping and the library is ready for external users, you'll want to start using PyPI instead.

Git dependencies are limited in that they don't allow for sophisticated dependency resolution. You can only specify an exact reference (tag, commit, or branch). You can't specify a version range. This is problematic if your library has dependencies, as having to request a specific version of your library makes it more likely that any dependency clashes will require manual intervention. It becomes even more problematic if your library may be depended on by other charm libraries. Requesting an exact hash or a branch tip may be sufficient for team-internal projects and prototyping, but proper versioning support is critical when sharing your library more widely, which will require promoting your package to PyPI.

###### How To

You'll need to include git in your charm's build dependencies to use a GitHub-hosted library in your charm:

```
parts:
  charm:
    build-packages: [git]
```

Then you can specify the dependency in your requirements like this:

```
ops @ git+https://github.com/canonical/operator@main
```

If you don't specify a branch or tag, it will default to main. This is probably sufficient for early prototyping and internal use. If you push git tags for releases or do releases on GitHub, you could point to the exact release tag, e.g. @2.18.1.Another approach which could be useful for prototyping would be to pin on a branch, e.g. stable/candidate/beta/edge, dev/main, v0/v1/v2 etc. These approaches may be useful as your library stabilises internally, but if you find yourself thinking about a scheme like this, it's probably a sign to just switch to PyPI and use semantic versioning.

If your package is in a subdirectory of your repository (for example if you use a monorepo, or collect your libraries into a single repository - or if you're just developing in your charm's repository while prototyping):

```
ops-testing @ git+https://github.com/canonical/operator@main#subdirectory=testing
```

If you're using pyproject.toml (recommended!):

```
[project]
dependencies = [
  "ops-testing @ git+https://github.com/canonical/operator@main#subdirectory=testing",
]
```

For poetry, see [here](https://python-poetry.org/docs/dependency-specification/#git-dependencies).

#### Dependencies

Declare \~= the lowest 2.X ops version that you support. This is broadly equivalent to >= 2.X, == 2.*. This futureproofs you against breaking changes in ops 3. There should be no need to declare a maximum ops version within the current 2.X releases, as ops respects semantic versioning and has a strong promise of backwards compatibility. When creating a new library, it's fine to declare the latest ops release as the minimum supported version, as charms are encouraged to always use the latest release of ops.

For other dependencies, ideally follow a similar approach. >= the lowest version that you need, < the next potential (or actual) breaking version. By keeping these dependencies permissive, you increase the number of charms that can use your library without worrying too much about their other dependencies.

## Charm Tech Action Items

#### Listing and best practices site

canonical-charmtech-charmlibs.readthedocs-hosted.com (nicer url coming someday?)

*A listing of libraries will be maintained by Charm Tech. (at ops.readthedocs.io/...? For now?) You can ping us on Matrix or Mattermost, or open an issue on the ops repository to ensure that new libraries are added to this listing. The purpose of this listing is to make it easier for charmers to avoid reinventing the wheel by seeing libraries that currently exist, as well as for us to highlight libraries that are actively recommended for solving various use cases (talking to a particular charm, handling file operations, etc). Charm Tech will review libraries when adding them to the listing, but you can also reach out to us for review and feedback anytime. Initially it is intended that Charm Tech will conduct reviews ourselves, but in future this process may involve members of other teams.*

Mention new libraries and new releases in your pulse reports. If you believe a library may be of interest to people outside your team, make a post on the Charmhub Discourse as well for the initial release, and feel free to do so for other releases too.

#### Template

You can find a template repository here. There's no need to actually initialise your repository from the template, but it would be good to use the readme format and ideally the basics of the linting and CI configuration as well. This will help Charm Tech run your library's tests against new and proposed ops changes to ensure backwards compatibility.

**TODO**: template - workflows (testing, publishing), pyproject.toml, tox.ini, README.md, CHANGES.md

### Charm Tech Action Items

* Make a list of charm libraries in our charmlibs docs as described above
* Publicise this listing and link to it from appropriate places (e.g. charmhub)
* Create a template for a charm library python package
