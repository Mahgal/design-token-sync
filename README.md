# design-token-sync

Turn a design-tokens JSON file into CSS custom properties and a Tailwind v4 `@theme` block, with validation — so a token file is the single source of truth for both plain CSS and Tailwind.

## Quick start

Requires Python 3.12+, standard library only — no dependencies, no network.

```bash
# Validate only
python -m design_token_sync examples/tokens.json --check

# Generate both outputs
python -m design_token_sync examples/tokens.json \
  --css examples/tokens.css \
  --tailwind examples/theme.css
```

## Example output

Real `--check` report from `examples/tokens.json` (11 tokens):

```
design-token-sync check
tokens: 11
errors: 0
warnings: 2
WARNING: duplicate value '4px' used by --radius-sm, --spacing-sm
WARNING: duplicate value '8px' used by --radius-md, --spacing-md
result: OK
```

The two warnings are expected: `4px` and `8px` legitimately appear in both
the `spacing` and `radius` groups. Warnings never block output; errors do.

Generated `examples/tokens.css` (real run, variables sorted, one per line):

```css
:root {
  --color-accent: #2563eb;
  --color-danger: #dc2626;
  --color-ink: #111111;
  --color-paper: #ffffff;
  --color-primary: #d4a017;
  --color-success: #16a34a;
  --radius-md: 8px;
  --radius-sm: 4px;
  --spacing-lg: 16px;
  --spacing-md: 8px;
  --spacing-sm: 4px;
}
```

`examples/theme.css` is the same variable list inside a Tailwind v4 `@theme { ... }` block.

## Supported input shapes

Both shapes produce identical variables. Nested groups flatten with `-`
(`color.primary` -> `--color-primary`).

**Flat nested groups:**

```json
{
  "color": {"primary": "#d4a017", "ink": "#111111"},
  "spacing": {"sm": "4px"}
}
```

**W3C-ish tokens with `$value` / `$type` leaves:**

```json
{
  "color": {"primary": {"$value": "#d4a017", "$type": "color"}},
  "spacing": {"sm": {"$value": "4px", "$type": "dimension"}}
}
```

## Validation rules

- Colour values (top-level `color` group, or `$type: "color"`) must be valid
  `#rgb` / `#rrggbb` / `#rrggbbaa` or `rgb()` / `rgba()` / `hsl()` / `hsla()`.
  Anything else is an **error**.
- A non-string leaf value (number, boolean, null, list, …) is an **error**.
- The same resolved value used by different token names is a **warning**
  (listed with every name that shares it).
- Empty groups are a **warning**.
- Spacing, size, radius and other non-colour values pass through unchanged.

The report prints `tokens`, `errors` and `warnings` counts, then one
`ERROR:` / `WARNING:` line per finding, then `result: OK` or `result: FAILED`.

## Exit codes

| Code | Meaning |
| ---- | ------- |
| 0 | Success — no validation errors (warnings allowed) |
| 1 | Validation errors found, input file missing/unreadable, or invalid JSON |
| 2 | Usage error (argparse) |

## Who this is for

Any project that keeps design tokens in JSON and wants them in CSS and
Tailwind without a build-tool chain. It pairs with agent-ready design
systems such as Meta's astrx: an agent can edit one token file and this
tool regenerates both the CSS variables and the Tailwind theme from it,
with validation catching bad values before they ship.

## License

MIT — see [LICENSE](LICENSE).
