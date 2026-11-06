"""Least squares through the origin, stdlib only (no numpy on the owner's Mac)."""
import itertools

RIDGE = 1e-9  # keeps the normal equations solvable when a token category never occurs


def fit(xs, ys):
    size = len(xs[0])
    normal = [[sum(row[i] * row[j] for row in xs) + (RIDGE if i == j else 0) for j in range(size)] for i in range(size)]
    target = [sum(row[i] * y for row, y in zip(xs, ys)) for i in range(size)]
    return solve(normal, target)


def solve(matrix, vector):
    size = len(vector)
    rows = [list(matrix[i]) + [vector[i]] for i in range(size)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda r: abs(rows[r][col]))
        rows[col], rows[pivot] = rows[pivot], rows[col]
        if rows[col][col] == 0:
            continue
        for r in range(size):
            if r != col:
                factor = rows[r][col] / rows[col][col]
                rows[r] = [a - factor * b for a, b in zip(rows[r], rows[col])]
    return [rows[i][size] / rows[i][i] if rows[i][i] else 0.0 for i in range(size)]


def r_squared(xs, ys, coefficients):
    """Uncentered R2, the right one for a fit through the origin."""
    residual = sum((y - sum(k * x for k, x in zip(coefficients, row))) ** 2 for row, y in zip(xs, ys))
    total = sum(y * y for y in ys)
    return 1 - residual / total if total else 0.0


def nonnegative_fit(xs, ys):
    """Least squares with every coefficient >= 0, exact for a handful of columns: solve each subset of columns
    and keep the best feasible one. A token can't lower the 5h %, and run 5 gave fresh input -52 unconstrained."""
    size = len(xs[0])
    best, best_residual = [0.0] * size, sum(y * y for y in ys)
    for count in range(1, size + 1):
        for columns in itertools.combinations(range(size), count):
            sub = fit([[row[c] for c in columns] for row in xs], ys)
            if min(sub) < 0:
                continue
            full = [0.0] * size
            for c, k in zip(columns, sub):
                full[c] = k
            residual = sum((y - sum(k * x for k, x in zip(full, row))) ** 2 for row, y in zip(xs, ys))
            if residual < best_residual:
                best, best_residual = full, residual
    return best
