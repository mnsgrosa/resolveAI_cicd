"""Script to send a Go coding pattern to the ResolveAI API."""

import httpx

API_URL = "http://localhost:8000"
API_KEY = "Jdnk5pJBOV7G1yYLFxtWRR1W-atuIXoE1XYGxOE7Q7o"  # Chave para patterns
OWNER = "mnsgrosa"
REPO = "ResolveAI-demos"

GO_PATTERNS = """# Go Coding Patterns

## Naming
- Use `CamelCase` for exported identifiers, `camelCase` for unexported
- Interface names: `-er` suffix (e.g., `Reader`, `Writer`)
- Package names: lowercase, single word, no underscores

## Error Handling
- Always check errors, never ignore them with `_` unless explicitly documented
- Use `fmt.Errorf("context: %w", err)` for error wrapping
- Define sentinel errors with `var ErrNotFound = errors.New("not found")`
- Return early on errors to avoid nesting

## Concurrency
- Use `context.Context` as first parameter for blocking operations
- Always document goroutine lifecycle and cancellation
- Use `sync.Mutex` or `sync.RWMutex` for shared state, prefer channels for communication
- Never start goroutines without a clear shutdown strategy

## Code Style
- Run `gofmt` or `goimports` before committing
- Use `go vet` and `staticcheck` for static analysis
- Keep functions under 40 lines when possible
- Add package-level godoc comments

## Security
- Never log sensitive data (tokens, passwords, keys)
- Use `crypto/rand` instead of `math/rand` for security-sensitive operations
- Validate and sanitize all external input
- Use prepared statements for database queries
"""


def main() -> None:
    payload = {"content": GO_PATTERNS}

    response = httpx.put(
        f"{API_URL}/api/v1/patterns/{OWNER}/{REPO}",
        json=payload,
        headers={"X-API-Key": API_KEY},
        timeout=10.0,
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")


if __name__ == "__main__":
    main()
