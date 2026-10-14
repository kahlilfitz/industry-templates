#!/usr/bin/env python3
"""Static check: messages never format untrusted input (quality-gate-criteria.md #8.9).

Every f-string, `%` or `.format` that reaches a `raise`, a `print` (or the tests' ASCII-safe `emit`), a `.write` (stderr), a list of reported problems or
an error-message generator may format only engine constants, field paths, indexes and counts. The check walks the AST
of every plugin script (the engines, the shared rules and the tests\\ tools) and judges each formatted value:

- constants, UPPER_CASE names and attributes, `len(...)`, arithmetic and joins of allowed values are allowed;
- content-free describers (`describe`, `show`, `os_reason`, `format_path`, `path_key`, `scenario_label`,
  `type(x).__name__`) are allowed;
- a plain name is allowed only when it is in SAFE_NAMES (each audited: a field path, index, count or engine constant)
  and every assignment to it in the enclosing function, including loop targets, is itself allowed;
- anything else (a raw value, an ID through `safe_token`, a dict lookup on an input record) is a violation.

A message built elsewhere is followed too: names in a sink are traced through their assignments, list appends and
`+=` within the function; a function parameter that reaches a message (directly, or by being passed on to another such
parameter) has every f-string argument checked at each call site; and functions named `*_problems` or `*_errors` have
every returned or yielded message checked.

Not scanned: `run_tests.py` and this file (test harness and checker: they print test names, file names of the plugin
itself and captured engine output, never review input) and the vendored, read-only `steering_guard.py`.

Scanned roots: the plugin root (--plugin-root, else PLUGIN_ROOT, else this submission folder) and this submission
folder's tests\\ folder (each script is scanned once when the two overlap).
"""
import ast
import os
import sys

PLUGIN_SLUG = "deliverable-review-quality-gate"
# The submission folder (tests/ lives here); the plugin's scripts live under the plugin root's skills/.
DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def plugin_root_from(argv):
    """--plugin-root DIR, else PLUGIN_ROOT, else the submission folder (the data root)."""
    value = None
    args = list(argv)
    for index, arg in enumerate(args):
        if arg == "--plugin-root" and index + 1 < len(args):
            value = args[index + 1]
        elif arg.startswith("--plugin-root="):
            value = arg.partition("=")[2]
    value = value or os.environ.get("PLUGIN_ROOT") or DATA_ROOT
    return os.path.abspath(value)


ROOT = plugin_root_from(sys.argv[1:])
SCAN_ROOTS = (ROOT, os.path.join(DATA_ROOT, "tests"))
EXCLUDED = {"run_tests.py", "check_messages.py", "steering_guard.py"}

# Names audited as field paths, positions, counts or engine constants wherever they are formatted into a message.
SAFE_NAMES = {
    # positions, indexes and line numbers
    "index", "position", "position_index", "first", "number", "differing",
    # counts, sizes and depths
    "count", "counts", "total", "drift", "depth", "max_depth", "spoofed", "unsupported", "limited",
    "blockers", "must_fix", "advisory", "advisories",
    # field paths and labels built from contract field names and indexes (path_key/format_path for member names)
    "label", "where", "path", "prefix", "id_key", "key", "shown", "rel", "side", "stage", "kind", "section_label",
    # engine constants: verdicts, gate IDs, severities and enum lists computed from constants
    "status", "gate", "severity", "missing", "repeated", "mismatched",
    # contract schema nodes and field names (the shipped contract, not input) in the validator
    "node", "option", "canonical", "root", "types", "field", "properties",
    # positions of IDs (never the IDs) in duplicate checks
    "positions", "repeat",
    # composed messages and caught engine errors (their own text is checked where it is built)
    "error", "exc", "name", "problems", "mismatches",
}
SAFE_FUNCS = {"str", "sorted", "min", "max", "abs",
              # plain-English expected type built from the shipped contract schema node (arguments are checked)
              "_type_phrase"}
# Content-free whatever their argument: a length, a count, a JSON type and size, an OS reason, a path whose member
# names pass path_key, a demo-scenario label, or positions.
DESCRIBERS = {"len", "sum", "describe", "show", "plural", "os_reason", "format_path", "path_key", "scenario_label",
              "repeated_positions", "type"}
# Audited per file: names safe only in the named script.
FILE_SAFE_NAMES = {}
SAFE_METHODS = {"join", "get", "items", "strip", "lstrip", "rstrip", "lower", "upper", "values", "keys", "count"}
SAFE_ATTRS = {"__name__", "lineno", "colno", "start", "msg"}
MESSAGE_LISTS = {"problems", "mismatches", "errors"}
# `emit` is the test scripts' ASCII-safe print, so a message passed to it is checked exactly like one passed to print.
PRINT_SINKS = {"print", "emit"}


def emit(line=""):
    """Print one line backslash-escaped to ASCII, so a cp1252 or ASCII console or pipe can always show it."""
    print(str(line).encode("ascii", "backslashreplace").decode("ascii"))


def is_constant_name(name):
    return name.isupper() or (name.startswith("_") and name[1:].isupper())


class FunctionScope:
    """Assignments within one function: name -> value expressions (loop targets map to their iterable)."""

    def __init__(self, node):
        self.assigned = {}
        self.safe_targets = set()
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = sub.targets if isinstance(sub, ast.Assign) else [sub.target]
                for target in targets:
                    self._bind(target, sub.value)
            elif isinstance(sub, (ast.For, ast.comprehension)):
                self._bind_loop(sub.target, sub.iter)
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr in ("append", "extend") \
                    and isinstance(sub.func.value, ast.Name):
                for arg in sub.args:
                    self.assigned.setdefault(sub.func.value.id, []).append(arg)
            elif isinstance(sub, ast.NamedExpr):
                self._bind(sub.target, sub.value)

    def _bind(self, target, value):
        if isinstance(target, ast.Name):
            self.assigned.setdefault(target.id, []).append(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts):
                for sub_target, sub_value in zip(target.elts, value.elts):
                    self._bind(sub_target, sub_value)
            else:
                for sub_target in target.elts:
                    self._bind(sub_target, value)

    def _bind_loop(self, target, iterable):
        # `for side, ids in (("raw pack", want), ...)`: bind element-wise across a literal of literals.
        if isinstance(target, ast.Tuple) and isinstance(iterable, (ast.Tuple, ast.List)) and iterable.elts \
                and all(isinstance(row, (ast.Tuple, ast.List)) and len(row.elts) == len(target.elts) for row in iterable.elts):
            for row in iterable.elts:
                for sub_target, sub_value in zip(target.elts, row.elts):
                    self._bind(sub_target, sub_value)
            return
        # `for index, item in enumerate(x)`: the index is a position whatever x is.
        if isinstance(iterable, ast.Call) and isinstance(iterable.func, ast.Name) and iterable.func.id == "enumerate" \
                and isinstance(target, ast.Tuple) and target.elts and isinstance(target.elts[0], ast.Name):
            self.safe_targets.add(target.elts[0].id)
            for sub_target in target.elts[1:]:
                self._bind(sub_target, iterable.args[0] if iterable.args else iterable)
            return
        self._bind(target, iterable)


class Checker:
    def __init__(self, path, tree):
        self.path = path
        self.file_names = FILE_SAFE_NAMES.get(os.path.basename(path), set())
        self.safe_names = SAFE_NAMES | self.file_names
        self.tree = tree
        self.violations = []
        self.functions = {}
        self.parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                self.parents[child] = node
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
        self.scopes = {}

    def scope_of(self, node):
        current = node
        while current in self.parents:
            current = self.parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                if current not in self.scopes:
                    self.scopes[current] = FunctionScope(current)
                return self.scopes[current]
        if self.tree not in self.scopes:
            self.scopes[self.tree] = FunctionScope(self.tree)
        return self.scopes[self.tree]

    def safe(self, expr, scope, seen):
        if expr is None or isinstance(expr, ast.Constant):
            return True
        if isinstance(expr, ast.Name):
            if is_constant_name(expr.id) or expr.id in scope.safe_targets or expr.id in self.file_names:
                return True
            if expr.id not in self.safe_names:
                return False
            if expr.id in seen:
                return True
            return all(self.safe(value, scope, seen | {expr.id}) for value in scope.assigned.get(expr.id, ()))
        if isinstance(expr, ast.Attribute):
            if is_constant_name(expr.attr) or expr.attr in SAFE_ATTRS:
                return True
            return False
        if isinstance(expr, ast.JoinedStr):
            return all(self.safe(value.value, scope, seen) for value in expr.values if isinstance(value, ast.FormattedValue))
        if isinstance(expr, ast.FormattedValue):
            return self.safe(expr.value, scope, seen)
        if isinstance(expr, ast.BinOp):
            return self.safe(expr.left, scope, seen) and self.safe(expr.right, scope, seen)
        if isinstance(expr, ast.UnaryOp):
            return self.safe(expr.operand, scope, seen)
        if isinstance(expr, ast.BoolOp):
            return all(self.safe(value, scope, seen) for value in expr.values)
        if isinstance(expr, ast.IfExp):
            return self.safe(expr.body, scope, seen) and self.safe(expr.orelse, scope, seen)
        if isinstance(expr, (ast.Tuple, ast.List, ast.Set)):
            return all(self.safe(value, scope, seen) for value in expr.elts)
        if isinstance(expr, ast.Subscript):
            # The output is an element of the container; the subscript only selects it.
            return self.safe(expr.value, scope, seen)
        if isinstance(expr, (ast.GeneratorExp, ast.ListComp, ast.SetComp)):
            # Only the element is output; loop targets are judged through their bindings.
            return self.safe(expr.elt, scope, seen)
        if isinstance(expr, ast.DictComp):
            return self.safe(expr.value, scope, seen)
        if isinstance(expr, ast.Dict):
            return all(self.safe(value, scope, seen) for value in expr.values)
        if isinstance(expr, ast.Compare):
            return True  # a boolean
        if isinstance(expr, ast.Call):
            func = expr.func
            args_safe = all(self.safe(arg, scope, seen) for arg in expr.args) and all(self.safe(kw.value, scope, seen) for kw in expr.keywords)
            if isinstance(func, ast.Name):
                if func.id in DESCRIBERS:
                    return True
                if func.id == "next" and expr.args and isinstance(expr.args[0], ast.Call) and is_message_function(expr.args[0].func):
                    return True  # the first message of a checked *_errors / *_problems generator
                if func.id in self.safe_names:
                    return self.safe(func, scope, seen)  # a path() callable
                return func.id in SAFE_FUNCS and args_safe
            if isinstance(func, ast.Attribute):
                if func.attr in DESCRIBERS:
                    return True
                if func.attr in SAFE_FUNCS:
                    return args_safe
                if func.attr in SAFE_METHODS:
                    return self.safe(func.value, scope, seen) and args_safe
            return False
        return False

    def report(self, node, expr):
        shown = os.path.basename(self.path)
        for scan_root in (ROOT, DATA_ROOT):
            if os.path.abspath(self.path).startswith(scan_root + os.sep):
                shown = os.path.relpath(self.path, scan_root)
                break
        self.violations.append(f"{shown}:{node.lineno}: {ast.unparse(expr)[:120]}")

    def check_message(self, node, expr):
        scope = self.scope_of(node)
        for sub in ast.walk(expr):
            if isinstance(sub, ast.FormattedValue):
                if not self.safe(sub.value, scope, frozenset()):
                    self.report(node, sub.value)
            elif isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Mod) and isinstance(sub.left, ast.Constant) and isinstance(sub.left.value, str):
                if not self.safe(sub.right, scope, frozenset()):
                    self.report(node, sub.right)
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "format" \
                    and isinstance(sub.func.value, ast.Constant):
                for arg in list(sub.args) + [kw.value for kw in sub.keywords]:
                    if not self.safe(arg, scope, frozenset()):
                        self.report(node, arg)
            elif isinstance(sub, ast.Name) and sub.id in self.safe_names and not isinstance(sub.ctx, ast.Store):
                # A name built elsewhere in the function: check the messages assigned to it.
                for value in scope.assigned.get(sub.id, ()):
                    if isinstance(value, (ast.JoinedStr, ast.BinOp, ast.List, ast.Call)) and value is not expr:
                        self.check_formats(node, value, scope)

    def check_formats(self, node, expr, scope):
        for sub in ast.walk(expr):
            if isinstance(sub, ast.FormattedValue) and not self.safe(sub.value, scope, frozenset()):
                self.report(node, sub.value)

    def run(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Raise) and node.exc is not None:
                self.check_message(node, node.exc)
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in PRINT_SINKS:
                    for arg in node.args:
                        self.check_message(node, arg)
                elif isinstance(func, ast.Attribute) and func.attr == "write" and "stderr" in ast.unparse(func.value):
                    for arg in node.args:
                        self.check_message(node, arg)
                elif isinstance(func, ast.Attribute) and func.attr in ("append", "extend") and isinstance(func.value, ast.Name) \
                        and func.value.id in MESSAGE_LISTS:
                    for arg in node.args:
                        self.check_message(node, arg)
                self.check_path_arguments(node)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id in MESSAGE_LISTS:
                self.check_message(node, node.value)
            elif isinstance(node, (ast.Return, ast.Yield)) and node.value is not None:
                function = self.enclosing_function(node)
                if function is not None and is_message_name(function.name):
                    self.check_message(node, node.value)
        return self.violations

    def enclosing_function(self, node):
        current = node
        while current in self.parents:
            current = self.parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return current
        return None

    def check_path_arguments(self, call):
        """A JoinedStr (or a lambda returning one) passed to a parameter that reaches a message (MESSAGE_PARAMS) is
        checked where it is built."""
        for param, value in bound_arguments(call):
            if isinstance(value, ast.Lambda):
                value = value.body
            if param in MESSAGE_PARAMS.get(callee_name(call), ()) and isinstance(value, ast.JoinedStr):
                self.check_message(call, value)


FUNCTIONS = {}
MESSAGE_PARAMS = {}


def is_message_name(name):
    return name.endswith("_problems") or name.endswith("_errors")


def is_message_function(func):
    name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return is_message_name(name)


def callee_name(call):
    return call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else None


def bound_arguments(call):
    target = FUNCTIONS.get(callee_name(call))
    if target is None:
        return []
    params = [arg.arg for arg in target.args.args]
    return list(zip(params, call.args)) + [(kw.arg, kw.value) for kw in call.keywords]


def sink_expressions(function):
    """Expressions in a function whose text reaches a message: raise, print, stderr writes, message-list appends and
    the returns/yields of a *_problems / *_errors function."""
    for node in ast.walk(function):
        if isinstance(node, ast.Raise) and node.exc is not None:
            yield node.exc
        elif isinstance(node, ast.Call):
            func = node.func
            if (isinstance(func, ast.Name) and func.id in PRINT_SINKS) \
                    or (isinstance(func, ast.Attribute) and func.attr == "write" and "stderr" in ast.unparse(func.value)) \
                    or (isinstance(func, ast.Attribute) and func.attr in ("append", "extend") and isinstance(func.value, ast.Name) and func.value.id in MESSAGE_LISTS):
                yield from node.args
        elif isinstance(node, (ast.Return, ast.Yield)) and node.value is not None and is_message_name(function.name):
            yield node.value


def compute_message_params():
    """Parameters whose value reaches a message, directly or by being passed to another such parameter (fixpoint)."""
    for name, function in FUNCTIONS.items():
        params = {arg.arg for arg in function.args.args}
        used = set()
        for expr in sink_expressions(function):
            used |= {sub.id for sub in ast.walk(expr) if isinstance(sub, ast.Name)} & params
        MESSAGE_PARAMS[name] = used
    changed = True
    while changed:
        changed = False
        for name, function in FUNCTIONS.items():
            params = {arg.arg for arg in function.args.args}
            for call in (node for node in ast.walk(function) if isinstance(node, ast.Call)):
                for param, value in bound_arguments(call):
                    if param in MESSAGE_PARAMS.get(callee_name(call), ()):
                        reached = {sub.id for sub in ast.walk(value) if isinstance(sub, ast.Name)} & params
                        if not reached <= MESSAGE_PARAMS[name]:
                            MESSAGE_PARAMS[name] |= reached
                            changed = True


def plugin_scripts():
    seen = set()
    for scan_root in SCAN_ROOTS:
        for path in scripts_under(scan_root):
            key = os.path.normcase(os.path.realpath(path))
            if key not in seen:
                seen.add(key)
                yield path


def scripts_under(scan_root):
    for folder, dirs, files in os.walk(scan_root):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "demo-data", "node_modules")]
        for name in sorted(files):
            if name.endswith(".py") and name not in EXCLUDED:
                yield os.path.join(folder, name)


def violations(paths=None):
    """(violations, scanned paths) for the plugin scripts, or for `paths` (tests point it at planted examples)."""
    FUNCTIONS.clear()
    MESSAGE_PARAMS.clear()
    trees = []
    for path in plugin_scripts() if paths is None else paths:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        trees.append((path, tree))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                FUNCTIONS.setdefault(node.name, node)
    compute_message_params()
    found = []
    for path, tree in trees:
        found += Checker(path, tree).run()
    return found, [path for path, _ in trees]


def main():
    found, scanned = violations()
    for line in found:
        emit(line)
    emit(f"check_messages: {len(scanned)} script(s) scanned, {len(found)} message format(s) outside engine constants, field paths, indexes and counts")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
