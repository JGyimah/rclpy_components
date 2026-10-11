# Contributing

Any contribution that you make to this repository will
be under the Apache 2 License, as dictated by that
[license](http://www.apache.org/licenses/LICENSE-2.0.html):

~~~
5. Submission of Contributions. Unless You explicitly state otherwise,
   any Contribution intentionally submitted for inclusion in the Work
   by You to the Licensor shall be under the terms and conditions of
   this License, without any additional terms or conditions.
   Notwithstanding the above, nothing herein shall supersede or modify
   the terms of any separate license agreement you may have executed
   with Licensor regarding such Contributions.
~~~

## Before opening a pull request

Run the tests, which include the linters this package is checked by:

```
python3 -m pytest test/
```

A change should keep all of them passing. `ament_copyright`, `ament_flake8`
and `ament_pep257` are part of that suite, so style is checked along with
behaviour and there is no separate step to remember.

New behaviour needs a test. The existing ones are a guide to the level: they
cover what a reader would not expect, such as a component class that inherits
`object.__init__` and so appears to accept any argument, rather than
restating what the code plainly does.

Every source file carries the Apache-2.0 header, which `ament_copyright`
enforces.
