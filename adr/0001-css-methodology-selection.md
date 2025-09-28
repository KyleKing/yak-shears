# 0001: CSS Methodology Selection

## Status

Accepted

## Context

As the project grows from small to medium scale, inline CSS scattered across templates becomes increasingly difficult to maintain. The original approach of embedding styles directly in Jinja2 templates creates several issues:

- Maintenance burden: Styles are mixed with HTML structure, making changes tedious
- Inconsistency: No enforced naming conventions across components
- Reusability: Common patterns can't be easily shared between templates
- Performance: Inline styles prevent browser caching benefits
- Developer experience: Difficult to locate and modify specific component styles

### Project Requirements

- Multiple templates (files list, editor, authentication)
- Growing component complexity (cards, pagination, forms)
- Server-side rendering with Jinja2 templates
- Static asset serving capability
- Target of maintaining under 14KB total CSS size

## Decision

Selected: BEM (Block Element Modifier)

We will use BEM methodology for organizing and naming CSS classes throughout the project.

## Rationale

BEM was chosen for the following reasons:

1. Perfect fit for project size: Medium complexity with clear component boundaries
1. Excellent maintainability: Component relationships are immediately clear from class names
1. Low learning curve: Simple, predictable naming convention
1. No build process required: Works with plain CSS files
1. Template readability: Class names clearly indicate component structure
1. Scalability: Easy to extend as the project grows
1. Developer experience: New contributors can quickly understand the codebase

## Alternatives Considered

### OOCSS (Object-Oriented CSS)

- Approach: Separate structure and skin, using multiple classes per element
- Example: <div class="card card--bordered card--shadow">
- Pros: Highly reusable, small CSS footprint
- Cons: Requires multiple classes per element, can be verbose in templates
- Why not chosen: Too verbose for templates, harder to maintain component relationships

### SMACSS (Scalable and Modular Architecture for CSS)

- Approach: Categorize CSS into base, layout, module, state, and theme
- Example: .card {} (module), .card.is-active {} (state)
- Pros: Clear organization by purpose, scalable structure
- Cons: More complex file organization, steeper learning curve
- Why not chosen: Overkill for medium project, more complex than needed

### SUIT CSS

- Approach: Component-based with strict naming conventions
- Example: .Card {} (component), .Card-title {} (descendant), .Card--large {} (modifier)
- Pros: Very strict conventions, excellent for large teams
- Cons: Verbose naming, overkill for medium projects
- Why not chosen: Too strict and verbose for our project size

### Utility-First (Tailwind CSS)

- Approach: Low-level utility classes combined in HTML
- Example: <div class="border rounded p-4 shadow hover:shadow-lg">
- Pros: Rapid development, small final CSS size
- Cons: Requires build process, HTML becomes style-heavy
- Why not chosen: Requires build process, makes HTML less semantic

## Implementation

### BEM Naming Convention

```
.block {}                    /* Block: standalone component */
.block__element {}           /* Element: part of a block */
.block--modifier {}          /* Modifier: variant of block/element */
```

## Key Implementation Rules

1. One Block per Component: Each major UI component gets its own block
1. Flat Element Hierarchy: Use \_\_ only for direct children, avoid deep nesting
1. Modifier for Variations: Use -- for different states or variants
1. Component Isolation: Each block should be self-contained
1. Consistent Naming: Use kebab-case for multi-word names
1. File Separation: Keep related styles together in component files

## Consequences

### Positive

- Predictable Structure: Class names reveal component hierarchy
- Easy Refactoring: Changes are localized to specific components
- Team Consistency: Clear conventions prevent naming conflicts
- Maintainable Growth: New features follow established patterns
- Performance: Static CSS files enable browser caching

### Negative

- Longer class names: BEM names are more verbose than generic names
- Learning curve: New team members need to learn BEM conventions
- File organization: Requires discipline in maintaining component boundaries

## Compliance

- All new CSS must follow BEM naming conventions
- Each component should have its own CSS file
- Inline styles are prohibited except for dynamic values
- CSS files should be imported through main.css

## Notes

This decision will be revisited if the project grows significantly or if team size increases substantially, at which point SUIT CSS or SMACSS might provide better governance.
