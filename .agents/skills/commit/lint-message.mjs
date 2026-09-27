#!/usr/bin/env node
/*
 * Checks a commit message against this repository's convention, and derives
 * scope candidates from the staged diff.
 *
 *   node .agents/skills/commit/lint-message.mjs <file>   # lint a message file
 *   node .agents/skills/commit/lint-message.mjs -        # lint stdin
 *   node .agents/skills/commit/lint-message.mjs --suggest
 *
 * It is also a working `commit-msg` hook: git passes the message path as $1.
 *
 * The convention is conventional-commit structure with Korean prose. Type and
 * scope stay English because they are the convention's own vocabulary and get
 * read by tooling; everything a person reads is Korean.
 */
import { readFileSync } from "node:fs"
import { execFileSync } from "node:child_process"

const TYPES = ["feat", "refactor", "fix", "docs", "style", "test", "chore"]

// Hangul syllables and compatibility jamo. The check is "does a human-facing
// line actually contain Korean", not "is it grammatical".
const HANGUL = /[가-힣㄰-㆏]/

const HEADER = new RegExp(`^(${TYPES.join("|")})\\(([a-z0-9][a-z0-9._/-]*)\\): (.+)$`)

/*
 * Header length is measured in terminal columns, not characters.
 *
 * Hangul, kana and CJK render double-width, so a 72-character Korean summary
 * occupies 101 columns and wraps in `git log --oneline` on a normal terminal.
 * Counting `.length` would call that fine. This is the one place where a rule
 * borrowed from English commit conventions does not transfer unchanged.
 */
const WIDE = /[\uAC00-\uD7A3\u3130-\u318F\u4E00-\u9FFF\u3040-\u30FF\uFF00-\uFF60]/
const columns = (text) => [...text].reduce((w, c) => w + (WIDE.test(c) ? 2 : 1), 0)
const TRAILER = /^[A-Za-z][A-Za-z-]*: .+$/

/*
 * Scope candidates, most specific first. A scope names the thing that changed
 * in the reader's vocabulary, which is not always the directory — `plugin/src`
 * is a build detail, `harness` is the thing.
 *
 * Edit this when the repository's shape changes; `--suggest` is only as good as
 * this table.
 */
const SCOPES = [
  [/^plugin\/src\/ui\//, "ui"],
  [/^plugin\/src\/harness\//, "harness"],
  [/^plugin\/src\/context\//, "context"],
  [/^plugin\/src\/tools\//, "tools"],
  [/^plugin\/src\/providers\//, "providers"],
  [/^plugin\/src\/obsidian\//, "obsidian"],
  [/^plugin\/src\/settings\//, "settings"],
  [/^plugin\/src\/view\//, "view"],
  [/^plugin\/src\/styles\//, "styles"],
  [/^plugin\/(build\.mjs|package\.json|tsconfig|vitest|\.dependency)/, "build"],
  [/^plugin\/tests\//, "test"],
  [/^plugin\/src\/main\.ts$/, "plugin"],
  [/^design-system\/src\/styles\//, "styles"],
  [/^design-system\//, "design-system"],
  [/^(docs\/|README\.md|CONTEXT\.md)/, "docs"],
  [/^(\.github\/|manifest\.json|versions\.json|scripts\/version-bump)/, "release"],
  [/^(\.agents\/|\.claude\/)/, "skills"],
  [/^model\//, "model"],
  [/^scripts\//, "scripts"],
]

function scopeFor(path) {
  for (const [pattern, scope] of SCOPES) if (pattern.test(path)) return scope
  // A file at the root belongs to the repository itself; anything else falls
  // back to its top-level directory, which is usually close enough to start from.
  return path.includes("/") ? path.split("/")[0] : "repo"
}

/*
 * Groups a scope's staged paths by their immediate parent directory, which is
 * the unit a commit should cover once the scope itself has been decided.
 *
 * A directory that owns more than one changed file becomes one group (commit
 * everything under it together). A directory that owns exactly one changed
 * file has no sibling to group with, so it is not treated as a shared folder
 * — it falls back to a file-level group instead.
 */
function groupByDirectory(paths) {
  const byDir = new Map()
  for (const path of paths) {
    const dir = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : ""
    if (!byDir.has(dir)) byDir.set(dir, [])
    byDir.get(dir).push(path)
  }

  const groups = []
  for (const [dir, files] of byDir) {
    groups.push(files.length > 1 ? { unit: dir, paths: files } : { unit: null, paths: files })
  }
  return groups
}

function suggest() {
  const staged = execFileSync("git", ["diff", "--cached", "--name-only"], { encoding: "utf8" })
    .split("\n")
    .filter(Boolean)

  if (staged.length === 0) {
    console.log("Nothing staged. `git add` first, or pass a message file to lint.")
    return 0
  }

  const byScope = new Map()
  for (const path of staged) {
    const scope = scopeFor(path)
    if (!byScope.has(scope)) byScope.set(scope, [])
    byScope.get(scope).push(path)
  }

  const ranked = [...byScope].sort((a, b) => b[1].length - a[1].length)
  console.log(`${staged.length} staged files across ${ranked.length} scope(s):\n`)
  for (const [scope, paths] of ranked) {
    console.log(`  ${scope.padEnd(16)} ${paths.length} file(s)`)
  }
  console.log()
  if (ranked.length > 1) {
    console.log("More than one scope. Prefer splitting into one commit per scope;")
    console.log("commit them separately rather than inventing a scope that covers both.")
    console.log()
  }

  // Within each scope, a single commit is still too coarse if the changed
  // files don't share a folder. Suggest one commit per directory, falling
  // back to one commit per file where a directory has no sibling.
  let anySplit = false
  for (const [scope, paths] of ranked) {
    const groups = groupByDirectory(paths)
    if (groups.length <= 1) continue
    anySplit = true
    console.log(`Scope "${scope}" has no single shared folder; commit by unit instead:`)
    for (const group of groups) {
      console.log(`  ${group.unit ?? "(no sibling — commit by file)"}`)
      for (const path of group.paths) console.log(`    ${path}`)
    }
    console.log()
  }

  if (ranked.length === 1 && !anySplit) {
    console.log(`Use: ${ranked[0][0]}`)
  }
  return 0
}

function lint(raw) {
  // git leaves its own comment lines in COMMIT_EDITMSG.
  const lines = raw.replace(/\r\n/g, "\n").split("\n").filter((l) => !l.startsWith("#"))
  while (lines.length && lines.at(-1).trim() === "") lines.pop()

  const errors = []
  const warnings = []
  const at = (i, message) => errors.push(`line ${i + 1}: ${message}`)

  if (lines.length === 0) {
    errors.push("The message is empty.")
    return { errors, warnings }
  }

  const header = lines[0]
  const match = HEADER.exec(header)
  if (!match) {
    at(0, `header must be \`type(scope): summary\`, got: ${JSON.stringify(header)}`)
    const loose = /^(\w+)(\([^)]*\))?:/.exec(header)
    if (loose && !TYPES.includes(loose[1])) {
      errors.push(`  "${loose[1]}" is not a type. Use one of: ${TYPES.join(", ")}`)
    } else if (loose && !loose[2]) {
      errors.push("  the scope in parentheses is required, e.g. `fix(harness): …`")
    }
  } else {
    const summary = match[3]
    const width = columns(header)
    if (width > 100) at(0, `header is ${width} columns wide (${header.length} chars); keep it under 100`)
    else if (width > 72) warnings.push(`line 1: header is ${width} columns wide (${header.length} chars); 72 or fewer reads better in \`git log --oneline\``)
    if (summary.endsWith(".")) at(0, "summary must not end with a period")
    if (!HANGUL.test(summary)) at(0, "summary must be written in Korean")
  }

  if (lines.length === 1) {
    errors.push("the message needs a body: a blank line, then `* ` bullets describing each change")
    return { errors, warnings }
  }

  if (lines[1].trim() !== "") at(1, "line 2 must be blank, separating the header from the body")

  const body = lines.slice(2)
  // Trailers (Co-Authored-By: …) sit at the end, after the bullets.
  let end = body.length
  while (end > 0 && (TRAILER.test(body[end - 1]) || body[end - 1].trim() === "")) end--
  const bulletLines = body.slice(0, end)

  const bullets = bulletLines.filter((l) => l.startsWith("* "))
  if (bullets.length === 0) {
    errors.push("the body needs at least one `* ` bullet describing a specific change")
    for (const [i, line] of bulletLines.entries()) {
      if (/^\s*[-•]\s/.test(line)) at(i + 2, "use `* ` for bullets, not `-` or `•`")
    }
  }

  for (const [i, line] of bulletLines.entries()) {
    if (line.trim() === "") continue
    const index = i + 2
    if (!line.startsWith("* ")) {
      if (!/^\s*[-•*]\s/.test(line)) at(index, `body lines must be \`* \` bullets, got: ${JSON.stringify(line)}`)
      continue
    }
    const text = line.slice(2).trim()
    if (text === "") at(index, "empty bullet")
    else if (!HANGUL.test(text)) at(index, "bullets must be written in Korean")
    if (text.endsWith(".")) warnings.push(`line ${index + 1}: bullets read better without a trailing period`)
  }

  return { errors, warnings }
}

const arg = process.argv[2]
if (arg === "--suggest") {
  process.exit(suggest())
}
if (!arg) {
  console.error("usage: lint-message.mjs <file> | - | --suggest")
  process.exit(2)
}

const raw = arg === "-" ? readFileSync(0, "utf8") : readFileSync(arg, "utf8")
const { errors, warnings } = lint(raw)

for (const warning of warnings) console.error(`warning  ${warning}`)
for (const error of errors) console.error(`error    ${error}`)

if (errors.length > 0) {
  console.error(`\n${errors.length} problem(s). The convention:\n`)
  console.error("  type(scope): 한국어 요약")
  console.error("")
  console.error("  * 무엇을 바꿨는지 한 줄")
  console.error("  * 또 무엇을 바꿨는지 한 줄")
  console.error(`\n  type is one of: ${TYPES.join(", ")}`)
  process.exit(1)
}
console.error(warnings.length > 0 ? "ok (with warnings)" : "ok")
