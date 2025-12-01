# PERF401: Use List Comprehension

Automatically converts for-loops with `append()` to list comprehensions for better performance.

## Pattern

Converts:
```python
var = []
for item in iterable:
    var.append(expr)
```

To:
```python
var = [expr for item in iterable]
```

## Example

Before:
```python
tags = []
for match in TAG_RE.finditer(content):
    tags.append(match.group(1))
return tags
```

After:
```python
tags = [match.group(1) for match in TAG_RE.finditer(content)]
return tags
```

## Usage

```bash
# Install grit (if not already installed)
npm install -g @getgrit/launcher

# Apply the pattern
grit apply perf401_list_comprehension

# Or check what would change
grit check perf401_list_comprehension
```
