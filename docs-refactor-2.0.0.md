2.0.0 refactor branch architecture

The public MonarchMoney class and existing imports remain in monarchmoney/monarchmoney.py. Authentication, session persistence, GraphQL transport, exceptions, and constants stay there. Purpose modules hold accounts, budgets, household, transactions, uploads, merchants, goals, recurring, credit, rules, and activity methods. The facade copies each method onto MonarchMoney itself after composing the mixins; this preserves direct-class lookup and common monkeypatch/subclass patterns.

All 63 formerly inline GraphQL documents and the 9 existing documents live in monarchmoney/queries/<purpose>/*.graphql. _query accepts both purpose/name and the 9 legacy flat names. New operations should use a purpose path. setup.py discovers the purpose packages, and MANIFEST.in includes their documents in source distributions.

Tests under tests/compatibility compare 104 method signatures captured from the 1.7.1 dev/main-identical baseline. tests/queries checks canonical extracted document ASTs and legacy aliases. Existing behavioral tests remain, with merchant pagination under tests/merchants. No live financial writes are part of the test suite.

Compatibility scope: method signatures/default kinds, public imports, exception identities, read_api's current ReadApiMixin alias, query text, packaging, session/auth behavior covered by existing tests, and representative return schemas are protected. Python function __module__/__qualname__ and source file paths now identify purpose modules. Custom monkeypatches of private rule-fragment constants no longer rewrite the extracted static query resources. The pre-1.7.1 Protocol behavior of ReadApiMixin was already absent in 1.7.1 and is not restored by this branch. A live Monarch account integration run and all third-party subclass/monkeypatch combinations have not been exercised.

This branch is groundwork only. The package version remains 1.7.1 until an explicitly requested future release process; nothing from this branch is deployed or published.
