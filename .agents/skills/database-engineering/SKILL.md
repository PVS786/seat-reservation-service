---

name: database-engineering
description: Designs, implements, reviews, and evolves the relational database layer using SQLAlchemy and migrations. Use for schema design, constraints, indexes, queries, transactions, locking, migrations, connection management, data integrity, or database-related performance changes.
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Database Engineering

## Purpose

This skill governs changes to the relational database layer.

The database should provide durable storage, enforce important invariants, and support correct concurrent behavior without introducing unnecessary complexity.

Priorities:

1. Data integrity
2. Correct transactional behavior
3. Clear relational modeling
4. Simplicity
5. Query efficiency
6. Maintainability
7. Performance supported by measurement

---

## Before Changing the Database

Inspect:

1. `docs/requirements.md`
2. `docs/architecture.md`
3. `docs/decisions.md`
4. existing models
5. existing migrations
6. relevant tests

Before making a schema or transaction change, identify:

* the business fact being stored;
* which entity owns that fact;
* whether the value is authoritative or derived;
* required relationships;
* required integrity constraints;
* concurrency implications;
* migration and rollback implications.

Do not silently redesign existing domain state.

---

## Relational Modeling

Use clear domain entities and relationships.

Prefer:

* primary keys;
* foreign keys;
* unique constraints;
* composite unique constraints;
* appropriate nullability;
* check constraints where useful;
* normalized relationships.

Do not store the same authoritative business fact in multiple places unless there is a deliberate reason to maintain the duplication.

For every stored field, be able to answer:

> What business fact does this column represent, and which component is responsible for keeping it correct?

Avoid storing values that can safely and cheaply be derived from authoritative state.

When a value is intentionally denormalized, document:

* why it is stored;
* who updates it;
* how concurrent updates remain consistent;
* how it is reconciled.

---

## Constraints

Use database constraints for invariants that the database can enforce reliably.

Prefer constraints for:

* uniqueness;
* required values;
* valid relationships;
* basic domain restrictions.

Examples include:

```text
PRIMARY KEY
FOREIGN KEY
UNIQUE
COMPOSITE UNIQUE
NOT NULL
CHECK
```

Do not rely solely on application code for an invariant that can be enforced by the database.

Application validation should still provide useful client-facing errors, but database constraints remain the final integrity boundary.

---

## Transactions

A transaction should represent one logical atomic state change.

A transaction should:

* perform all required related changes;
* commit only when the complete operation is valid;
* roll back cleanly on failure.

Keep transactions as short as practical.

Avoid:

* network calls;
* long-running computation;
* unnecessary logging;
* unrelated work

inside critical transactions.

Do not hide important transaction boundaries inside unrelated helper methods.

When modifying transaction behavior, explicitly consider:

* concurrent requests;
* rollback;
* retry behavior;
* partial updates;
* isolation behavior;
* lock ordering.

---

## Concurrency and Locking

Treat locking as a tool for protecting shared business state.

Before adding a lock, identify:

1. Which state is shared?
2. Which operations can conflict?
3. What transaction protects the state?
4. What must be serialized?
5. Can lock acquisition order become inconsistent?

Prefer the simplest mechanism that provides the required correctness.

When multiple rows or resources are protected together, use a deterministic ordering where required.

Do not introduce process-local locks as a substitute for database consistency.

Do not introduce specialized database locking mechanisms without first establishing that ordinary transactional and relational mechanisms cannot satisfy the requirement.

---

## Queries

Prefer:

* explicit column selection;
* parameterized queries;
* predictable query behavior;
* appropriate indexes;
* simple SQL that another engineer can understand.

Never construct SQL by concatenating untrusted input.

Avoid unnecessary ORM abstraction when the resulting query becomes harder to understand.

For correctness-critical queries, understand the generated SQL and its transaction behavior rather than relying blindly on ORM semantics.

---

## Indexing

Every index should have a reason.

Consider indexes for:

* primary-key lookups;
* foreign-key relationships;
* frequently queried columns;
* common filtering patterns;
* uniqueness requirements;
* ordered access patterns used by important queries.

Before adding an index, consider:

* query frequency;
* expected data volume;
* write overhead;
* index selectivity;
* whether an existing index already satisfies the access pattern.

Do not add indexes speculatively.

When a performance issue is suspected, measure the query before and after the change.

---

## Migrations

Every schema change must be represented by a migration.

A migration should be:

* deterministic;
* reviewable;
* safe to run on a clean database;
* consistent with the application's model definitions.

Before completing a migration:

1. Test applying it from the previous schema.
2. Test creating a fresh database from the migration history.
3. Verify relevant application tests.
4. Review destructive operations carefully.

Do not modify an already-applied migration merely to make the current local database work.

Create a new migration for subsequent schema changes.

---

## SQLAlchemy

Use SQLAlchemy as the persistence abstraction, while remaining aware of the SQL and transaction semantics underneath it.

Prefer:

* explicit session/transaction management;
* clear repository or persistence boundaries;
* parameterized statements;
* appropriate relationship loading;
* predictable query behavior.

Do not share mutable database sessions across concurrent application tasks.

Do not assume ORM operations are atomic merely because they are expressed as one Python statement.

When correctness depends on transaction ordering or locking, inspect the actual database operation being performed.

---

## Connection Management

Database connections are a finite resource.

Remember:

```text
HTTP concurrency != database connection count
```

Consider:

* pool size;
* connection acquisition;
* connection timeout;
* transaction duration;
* connection exhaustion;
* application worker count.

Do not increase the database pool blindly to handle more HTTP concurrency.

Long transactions and unnecessary locks can reduce throughput even when the application has available CPU.

---

## Error Handling

Distinguish:

### Domain conflicts

Examples:

```text
seat unavailable
booking limit exceeded
duplicate idempotency request
```

These should be converted into intentional application-level responses.

### Database/infrastructure failures

Examples:

```text
connection failure
transaction failure
unexpected database error
```

These must not be silently swallowed.

Preserve enough context for diagnosis while avoiding sensitive information in logs or API responses.

---

## ORM and Database Integrity

Never assume that application-level checks alone guarantee correctness.

For example, this pattern is unsafe under concurrency:

```text
SELECT ...
if result is valid:
    INSERT ...
```

unless the surrounding transaction and database constraints provide the required serialization.

When a rule must remain true under concurrent requests, identify the database mechanism that makes the rule enforceable.

---

## Data Types

Use appropriate database types for the business domain.

For monetary values:

```text
integer paise
```

Do not use floating-point types for monetary state.

Use timestamps consistently and define timezone behavior explicitly.

Do not encode business state into ambiguous strings when a constrained value set is sufficient.

---

## Database-Aware Performance

Optimize only when there is an observed or clearly expected bottleneck.

For important queries, consider:

* execution plan;
* indexes;
* row counts;
* lock duration;
* transaction duration;
* connection usage.

Do not trade away correctness for speculative throughput.

For a high-contention operation, prioritize:

```text
correctness
→ predictable contention
→ short transactions
→ measured optimization
```

---

## Schema Change Checklist

Before approving a schema change, answer:

1. What business fact does this change represent?
2. Which table owns that fact?
3. Is the data authoritative or derived?
4. What constraints protect it?
5. What indexes are actually required?
6. What happens concurrently?
7. What happens if the transaction fails?
8. How is the migration applied safely?
9. Can the same fact accidentally exist in conflicting locations?
10. What tests demonstrate the expected behavior?

---

## Agent Workflow

For database-related tasks:

```text
inspect
→ identify business fact
→ review existing schema
→ evaluate constraints
→ evaluate transaction/concurrency impact
→ propose smallest appropriate change
→ implement
→ create/update migration
→ add tests
→ run tests
→ review generated SQL/queries where relevant
```

Before making a non-trivial change, briefly explain:

* what data is changing;
* why the change belongs in the database;
* what constraints protect it;
* how concurrency is handled;
* what migration is required.

After implementation, report:

* schema changes;
* migration changes;
* relevant tests;
* any performance or concurrency considerations.
