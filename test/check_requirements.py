# Copyright 2026 Jude Gyimah
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Fail if any test module would be dropped for a missing dependency.

conftest.py drops a module whose imports fail, which is silence rather than a
failure: the run collects what is left and still reports green. A jazzy job
once passed here having run 16 of 56 tests, because two modules needed a
package that was not installed and nothing said so.

This asks conftest itself what it would drop, rather than keeping a second
copy of the requirements that could drift from it, and names the import that
failed. CI runs it before the tests, so an environment that is meant to have
the runtime fails loudly instead of quietly shrinking the suite.
"""

import importlib
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_conftest():
    """Load conftest.py by path, without putting it on sys.path."""
    spec = importlib.util.spec_from_file_location(
        'rclpy_components_conftest', os.path.join(HERE, 'conftest.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    """Report what cannot be collected, and whether that is fatal."""
    conftest = load_conftest()

    if not conftest.collect_ignore:
        print('all %d test modules can be collected' % len(conftest.REQUIREMENTS))
        return 0

    print('These test modules would be dropped, leaving a short green run:')

    for module in conftest.collect_ignore:
        for requirement in conftest.REQUIREMENTS[module]:
            try:
                importlib.import_module(requirement)
            except Exception as error:  # noqa: B902 - whatever broke is the answer
                print('  %s needs %s: %s: %s'
                      % (module, requirement, type(error).__name__, error))
                break

    return 1


if __name__ == '__main__':
    sys.exit(main())
