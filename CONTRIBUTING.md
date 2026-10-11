# Contributing

Contributions are welcome, by issue or pull request.

## Before opening a pull request

Run the tests, which include the linters this package is checked by:

```
python3 -m pytest test/
```

A change should keep all of them passing. `ament_copyright`, `ament_flake8` and
`ament_pep257` are part of that suite, so style is checked along with
behaviour; there is no separate step to remember.

New behaviour needs a test. The existing ones are a guide to the level: they
cover what a reader would not expect, such as a component class that inherits
`object.__init__` and so appears to accept any argument, rather than restating
what the code plainly does.

## Licence

This package is Apache-2.0, and a contribution is taken to be under the same
terms. Every source file carries the licence header, which `ament_copyright`
enforces.
