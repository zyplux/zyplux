# 10. [Reserving PascalCase consts for schemas, components, and allowed factories](10-no-stray-pascal-const.test.ts)

## 10.1 flagging misnamed zod schemas

1. 10.1.1 flags a z-rooted schema missing the Schema suffix or written in camelCase
2. 10.1.2 flags a chained z-rooted schema and one behind a satisfies annotation
3. 10.1.3 flags a schema from a custom factory, detected by type rather than z syntax
4. 10.1.4 flags a schema composed off another schema
5. 10.1.5 flags a schema pulled out by destructuring

## 10.2 flagging stray PascalCase consts

### 10.2.1 flags a PascalCase const from an unrecognized factory or holding a plain object

## 10.3 permitting well-named schemas

1. 10.3.1 allows PascalCase schemas with the Schema suffix, plain or chained
2. 10.3.2 allows a composed schema with a valid name
3. 10.3.3 allows a destructured schema renamed to a valid name

## 10.4 permitting non-schema names that are not PascalCase or not stray

1. 10.4.1 ignores camelCase values, UPPER_CASE constants, and non-schema destructured PascalCase
2. 10.4.2 allows results of the default factory allowlist
3. 10.4.3 allows a factory added through the allowed factories option
4. 10.4.4 allows React components returning JSX or used as a JSX element in the same file
