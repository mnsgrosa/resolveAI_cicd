"""Script to test post_diff_comment directly against a real GitHub PR."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.github_service import post_diff_comment

# --- Configure these ---
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPOSITORY = "mnsgrosa/ResolveAI-demos"  # owner/repo
PR_NUMBER = 1  # must be an open PR in the repo
# -----------------------

SAMPLE_DIFF = """diff --git a/main.go b/main.go
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/main.go
@@ -0,0 +1,20 @@
+package main
+
+import (
+\t"fmt"
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
+func main() {
+\tfmt.Println(generateToken(32))
+}
diff --git a/utils.go b/utils.go
new file mode 100644
index 0000000..7654321
--- /dev/null
+++ b/utils.go
@@ -0,0 +1,12 @@
+package main
+
+func sanitize(s string) string {
+\tif s == "" {
+\t\treturn s
+\t}
+\treturn s
+}
+
+func process(items []string) []string {
+\treturn items
+}
"""


async def main() -> None:
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set.")
        print("Usage: GITHUB_TOKEN=<token> python scripts/test_diff_comment.py")
        return

    print(f"Posting diff comment to {REPOSITORY} PR #{PR_NUMBER}...")

    comment_id = await post_diff_comment(
        repository=REPOSITORY,
        pr_number=PR_NUMBER,
        diff_raw=SAMPLE_DIFF,
        github_token=GITHUB_TOKEN,
    )

    if comment_id:
        print(f"Comment posted successfully. ID: {comment_id}")
        print(f"View at: https://github.com/{REPOSITORY}/pull/{PR_NUMBER}")
    else:
        print("Failed to post comment.")


if __name__ == "__main__":
    asyncio.run(main())
