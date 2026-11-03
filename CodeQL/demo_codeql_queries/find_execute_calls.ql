/**
 * @name Find Dangerous Calls to Execute (Potential SQLi)
 * @description Finds calls to `.execute()` method in Python code
 * @kind problem
 * @problem.severity error
 * @id python/demo/dangerous-execute-call
 */

import python

from Call call, Attribute attr
where
  call.getFunc() = attr and
  attr.getName() = "execute"
select call, "Dangerous database query execution found: " + call.toString()
