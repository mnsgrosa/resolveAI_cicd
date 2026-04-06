"""Script to create a PR with Go code issues and trigger auto-review."""

import asyncio

import httpx

API_URL = "http://localhost:8000"
API_KEY = "Jdnk5pJBOV7G1yYLFxtWRR1W-atuIXoE1XYGxOE7Q7o"  # Chave gerada para o patterns
OWNER = "mnsgrosa"
REPO = "ResolveAI-demos"
GITHUB_TOKEN = "GITHUB_TOKEN"
# Sample diff with intentional Go issues for demonstration
GO_DIFF = """diff --git a/main.go b/main.go
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/main.go
@@ -0,0 +1,35 @@
+package main
+
+import (
+\t"fmt"
+\t"math/rand"
+\t"log"
+)
+
+var err_not_found = errors.New("not found")
+
+func GetUserData(id int, db *Database) (map[string]interface{}, error) {
+\tdata, err := db.Query(id)
+\t_ = err
+\t
+\tif data == nil {
+\t\treturn nil, err_not_found
+\t}
+\t
+\tresult := make(map[string]interface{})
+\tfor key, value := range data {
+\t\tresult[key] = value
+\t}
+\t
+\tfmt.Printf("Got data: %v\\n", data)
+\tlog.Printf("User data fetched with id: %d", id)
+\t
+\treturn result, nil
+}
+
+func startWorker() {
+\tgo func() {
+\t\tfor {
+\t\t\tprocessItems()
+\t\t}
+\t}()
+}
diff --git a/utils.go b/utils.go
new file mode 100644
index 0000000..7654321
--- /dev/null
+++ b/utils.go
@@ -0,0 +1,20 @@
+package main
+
+import (
+\t"math/rand"
+\t"time"
+)
+
+func generateToken(length int) string {
+\trand.Seed(time.Now().UnixNano())
+\tchars := "abcdefghijklmnopqrstuvwxyz0123456789"
+\tresult := ""
+\tfor i := 0; i < length; i++ {
+\t\tresult += string(chars[rand.Intn(len(chars))])
+\t}
+\treturn result
+}
+
+func Processitems(items []string) []string {
+\tvar output []string
+\tfor _, item := range items {
+\t\tif item != "" {
+\t\t\toutput = append(output, item)
+\t\t}
+\t}
+\treturn output
+}
"""


async def main() -> None:
    payload = {
        "repository": f"{OWNER}/{REPO}",
        "pr_number": None,
        "diff_raw": GO_DIFF,
        "base_ref": "main",
        "head_ref": "feature/go-example-with-issues",
        "github_token": GITHUB_TOKEN,
        "commit_sha": "abc123def456",  # ignored when create_pr=True — server uses real SHA
        "create_pr": True,
        "pr_title": "ResolveAI Auto-Review: Go Code Example",
        "pr_body": """## Auto-generated PR with Go code issues

This PR was automatically created by ResolveAI to demonstrate AI-powered code review.

The code contains intentional issues for demonstration purposes:
- Ignored errors
- Security concerns (using `math/rand` instead of `crypto/rand`)
- Goroutine without shutdown strategy
- Naming convention violations
- Missing imports
- Inefficient string concatenation

Please review the inline comments for detailed feedback.""",
    }

    print(f"Creating PR and triggering auto-review for {OWNER}/{REPO}...")
    print(f"API URL: {API_URL}/api/v1/auto-review")
    print("-" * 80)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_URL}/api/v1/auto-review",
            json=payload,
            headers={"X-API-Key": API_KEY},
        )

    print(f"Status Code: {response.status_code}")
    print("-" * 80)

    if response.status_code in (200, 201):
        data = response.json()
        print(f"✅ Success!")
        print(f"Review ID: {data.get('review_id')}")
        print(f"PR Number: {data.get('pr_number')}")
        print(f"PR URL: {data.get('pr_url')}")
        print(f"Comments Count: {data.get('comments_count')}")
        print(f"Report File: {data.get('report_file_path')}")
        print(f"\nSummary:\n{data.get('summary')}")
    else:
        print(f"❌ Failed!")
        print(f"Response: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
