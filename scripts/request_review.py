"""Script to send a code review request to the ResolveAI API."""

import httpx

API_URL = "http://localhost:8000"
API_KEY = "Jdnk5pJBOV7G1yYLFxtWRR1W-atuIXoE1XYGxOE7Q7o"  # Chave gerada pelo patterns
GITHUB_TOKEN = "GITHUB_TOKEN"

# A realistic Go diff with intentional issues for the AI to catch
DIFF_RAW = """diff --git a/internal/handler/user.go b/internal/handler/user.go
--- a/internal/handler/user.go
+++ b/internal/handler/user.go
@@ -12,6 +12,34 @@ import (
 \t"github.com/example/app/internal/db"
 )

+func GetUser(w http.ResponseWriter, r *http.Request) {
+\tid := r.URL.Query().Get("id")
+\tconn := db.GetConnection()
+\tdefer conn.Close()
+
+\tvar user User
+\terr := conn.QueryRow("SELECT * FROM users WHERE id = " + id).Scan(&user.ID, &user.Name, &user.Email)
+\tif err != nil {
+\t\tfmt.Println(err)
+\t\tw.WriteHeader(500)
+\t\tw.Write([]byte("error"))
+\t\treturn
+\t}
+
+\tjson.NewEncoder(w).Encode(user)
+}
+
+func CreateToken() string {
+\trand.Seed(time.Now().UnixNano())
+\tvar chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
+\tb := make([]byte, 32)
+\tfor i := range b {
+\t\tb[i] = chars[rand.Intn(len(chars))]
+\t}
+\treturn string(b)
+}
+
 func ListUsers(w http.ResponseWriter, r *http.Request) {
 \trows, err := db.Query("SELECT id, name, email FROM users")
 \tif err != nil {
"""

REQUEST_BODY = {
    "repository": "owner/repo",
    "pr_number": 42,
    "diff_raw": DIFF_RAW,
    "base_ref": "main",
    "head_ref": "feature/user-handler",
    "github_token": GITHUB_TOKEN,
    "commit_sha": "abc1234def5678",
}


def main() -> None:
    response = httpx.post(
        f"{API_URL}/api/v1/review",
        json=REQUEST_BODY,
        headers={"X-API-Key": API_KEY},
        timeout=60.0,  # AI review can take a while
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")


if __name__ == "__main__":
    main()
