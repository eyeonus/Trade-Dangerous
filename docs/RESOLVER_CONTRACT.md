# RESOLVER CONTRACT

Purpose: define the lookup and ambiguity behavior that must be preserved or deliberately changed during ORM-first migration.

## Mandatory behaviors to define
- `lookup_system`
- `lookup_station`
- `lookup_place`
- later `lookup_item`

## Input forms
Document expected handling for:
- `SYS`
- `STN`
- `SYS/STN`
- `/STN`
- `@` forms
- `@N` duplicate-system disambiguation

## Matching ladder
Fill in the adopted order here:
1. syntax parse and disambiguation handling
2. exact raw
3. exact normalized
4. prefix raw
5. prefix normalized
6. broader fallback only if still required

## Ambiguity behavior
Record:
- when ambiguity is raised
- candidate ordering rules
- candidate formatting

## Not-found behavior
Record the exact error or return behavior.

## Parity test matrix
List the cases that must become tests.
