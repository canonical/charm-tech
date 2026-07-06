# OP032 — Best practices for unit testing

| Field | Value |
| --- | --- |
| Status | Approved |
| Type | Standard |
| Created | Mar 13, 2023 |

## Abstract

This specification outlines a standard for writing unit tests. This includes why we write unit tests and a set of best practices to be followed.

## Rationale

As the number of projects grows at Canonical and we want to assure consistency and reliability for our customers, having standard ways of testing becomes crucial. In this context, it is important to define what are best practices for writing unit tests.

## Specification

### Definition

A unit test is code that validates the behavior of a unit of code. A unit is a small portion of code that can be exercised individually.

#### Purpose

Unit tests have the following purpose:

1. Help in development and design
2. Support maintenance over time
3. Allow for reliable refactoring

#### General Principles

Unit tests should be written with the following principles in mind. The decision to diverge from one of the best practices below should be motivated by one of those principles.

1. **Unit tests should take the point of view of the user[^1] of the code**
2. **Each unit test should validate exactly one behavior[^2]**
3. **Each behavior should be validated exactly once**

#### Properties

When following best practice, a unit tests suite displays the following properties:

1. Serves as documentation
2. Reduces the time spent in different, more expensive, test layers like integration tests and manual tests
3. Is fast to execute
4. Allows for secure refactoring
5. Provides valuable information to developers when performing code changes
6. Puts pressure on design

### Best practices

#### Coding practices

Unit tests are code and should follow the same practices as the rest of the source code. For example, this means that they should be subject to the same code quality verification process.

#### Structure

Unit tests should be structured in 3 sections:

1. **Arrange**: Create the required pre-conditions for running the test. It is possible for this section to be empty.
2. **Act**: Execute the method under test
3. **Assert**: Validate the actual result is the same as the expected result

For example:

```py
def test_balance_adjusted:
    account = BankAccount()
    transfer_amount = 5

    account.transfer_money(transfer_amount)

    assert account.balance == transfer_amount
```

#### Coupling

Unit tests should not require changes if the internal implementation of the code is changed and the behavior remains unchanged. Unit tests that require changes under those circumstances are considered "brittle". To achieve this, there should be limited coupling between unit tests and the code under test. Therefore:

* Unit tests should only target public interfaces
* Unit tests should validate behaviors. Acceptable validations are:
  * The output of the method under test is as expected
  * An HTTP call is made to the expected URL with the expected content
  * Another class's public method is called with the expected parameters
  * A file is changed with the expected content
* Unit tests should not validate the internal implementation of the code. Bad smells are:
  * Asserting that a private method is called
  * Private methods are patched

#### Mocking

To allow for fast running unit tests and ease of run, unit tests shouldn't involve databases, filesystems, external API's, etc. Each of these interactions should be mocked.

Keep the amount of mocks to a minimum. The use of multiple mocks for a unit test is a design smell and often points to the method under test being too complex. Monkey patched mocks in particular increase the coupling to the code under test and contribute to brittle tests.

#### Development

All unit tests must be runnable locally without relying on an external system like a CI pipeline.

#### Code changes

The addition/removal of features should be accompanied by the addition/removal of unit tests. If code changes don't impact the behavior of the code (like in refactoring), unit tests may not change.

#### Code coverage

While this standard discourages the use of specific code coverage targets, teams are free to pick a code coverage threshold at their own discretion if they believe it would benefit them. It is possible to exclude parts of the code that should not be measured by code coverage (ex. libraries). It is, however, encouraged to continuously validate that code changes do not significantly reduce the existing code coverage.

#### Pipeline integration

Passing unit tests should be part of the merge criteria for pull requests. This should be automatically enforced via the project's CI pipeline so that changes that break unit tests block merging to the project's main branch.
