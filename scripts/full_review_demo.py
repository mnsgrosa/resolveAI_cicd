"""Full review demo: creates a PR, runs AI review, posts inline comments + diff comment."""

import asyncio
import os
import sys

import httpx

API_URL = "http://localhost:8000"
API_KEY = "Jdnk5pJBOV7G1yYLFxtWRR1W-atuIXoE1XYGxOE7Q7o"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
OWNER = "mnsgrosa"
REPO = "ResolveAI-demos"

DIFF = """diff --git a/auth/handler.go b/auth/handler.go
new file mode 100644
index 0000000..aabbcc1
--- /dev/null
+++ b/auth/handler.go
@@ -0,0 +1,42 @@
+package auth
+
+import (
+\t"database/sql"
+\t"fmt"
+\t"math/rand"
+\t"net/http"
+\t"time"
+)
+
+var db *sql.DB
+
+func Login(w http.ResponseWriter, r *http.Request) {
+\tusername := r.FormValue("username")
+\tpassword := r.FormValue("password")
+
+\tquery := fmt.Sprintf("SELECT id FROM users WHERE username='%s' AND password='%s'", username, password)
+\trow := db.QueryRow(query)
+
+\tvar id int
+\terr := row.Scan(&id)
+\tif err != nil {
+\t\tw.WriteHeader(401)
+\t\treturn
+\t}
+
+\ttoken := generateSession()
+\thttp.SetCookie(w, &http.Cookie{Name: "session", Value: token})
+\tfmt.Fprintf(w, "welcome %s", username)
+}
+
+func generateSession() string {
+\trand.Seed(time.Now().UnixNano())
+\tb := make([]byte, 16)
+\tfor i := range b {
+\t\tb[i] = byte(rand.Intn(256))
+\t}
+\treturn fmt.Sprintf("%x", b)
+}
diff --git a/store/user.go b/store/user.go
new file mode 100644
index 0000000..ddeeff2
--- /dev/null
+++ b/store/user.go
@@ -0,0 +1,24 @@
+package store
+
+import "database/sql"
+
+type User struct {
+\tID       int
+\tUsername string
+\tPassword string
+}
+
+func GetAllUsers(db *sql.DB) ([]User, error) {
+\trows, err := db.Query("SELECT id, username, password FROM users")
+\tif err != nil {
+\t\treturn nil, err
+\t}
+\tdefer rows.Close()
+
+\tvar users []User
+\tfor rows.Next() {
+\t\tvar u User
+\t\trows.Scan(&u.ID, &u.Username, &u.Password)
+\t\tusers = append(users, u)
+\t}
+\treturn users, nil
+}
"""


async def main() -> None:
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set.")
        print("Usage: GITHUB_TOKEN=<token> .venv/bin/python scripts/full_review_demo.py")
        sys.exit(1)

    payload = {
        "repository": f"{OWNER}/{REPO}",
        "pr_number": None,
        "diff_raw": DIFF,
        "base_ref": "main",
        "head_ref": "feature/auth-handler-demo",
        "github_token": GITHUB_TOKEN,
        "commit_sha": "",
        "create_pr": True,
        "pr_title": "ResolveAI Demo: Auth handler with security issues",
        "pr_body": "Demo PR created by ResolveAI to test full review flow including diff comment.",
    }

    print(f"Sending to {API_URL}/api/v1/auto-review ...")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{API_URL}/api/v1/auto-review",
            json=payload,
            headers={"X-API-Key": API_KEY},
        )

    print(f"Status: {response.status_code}")
    print("-" * 60)

    if response.status_code in (200, 201):
        data = response.json()
        pr_url = data.get("pr_url")
        print(f"PR:            {pr_url}")
        print(f"Review ID:     {data.get('review_id')}")
        print(f"Comments:      {data.get('comments_count')}")
        print(f"Report file:   {data.get('report_file_path')}")
        print(f"\nSummary:\n{data.get('summary')}")
        if pr_url:
            print(f"\nOpen the PR to see inline comments + diff in the conversation tab:")
            print(f"  {pr_url}")
    else:
        print(f"Failed: {response.text}")


if __name__ == "__main__":
    asyncio.run(main())
