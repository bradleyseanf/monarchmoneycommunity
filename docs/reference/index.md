# Method directory

Search the site for a method name, or choose one below to see its signature,
parameters, defaults, docstring, and implementation. This directory and the
reference are generated from the current Python source during every build.

Use `await` for async methods. Session file helpers and configuration setters are
synchronous. Most base-client data methods return dictionaries containing the
GraphQL response fields; some operations return booleans or other values. The
signature and source show each method's contract. Dictionary annotations are not
a complete schema of Monarch's remote service.

Methods named `create_*`, `update_*`, `delete_*`, `set_*`, `archive_*`,
`unarchive_*`, `upload_*`, `reset_budget`, or `request_accounts_refresh*` may change account data,
local state, or trigger remote work. See the individual method before calling it.

Start with the [usage examples](../examples.md) or the
[typed-client guide](../typed-client.md) for complete workflows.

<!-- method-directory -->
