from flask import Flask, request, jsonify, render_template
import requests
import os

app = Flask(__name__)

class GitHubHandler:
    def __init__(self):
        self.base_url = "https://api.github.com"
    
    def get_issues(self, owner, repo, state='open'):
        url = f"{self.base_url}/repos/{crazyzia225}/{copilot_test}/issues"
        params = {'state': state, 'per_page': 10}
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            return response.json()
        return None

github = GitHubHandler()

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').lower()
    response = {"response": ""}
    
    if 'issues' in user_message and 'github' in user_message:
        # Extract repository info (basic parsing)
        if 'repo' in user_message:
            parts = user_message.split()
            try:
                repo_index = parts.index('repo') + 1
                repo_full = parts[repo_index]
                owner, repo_name = repo_full.split('/')
                
                issues = github.get_issues(owner, repo_name)
                if issues:
                    issue_list = []
                    for issue in issues[:5]:
                        if 'pull_request' not in issue:
                            issue_list.append(f"#{issue['number']}: {issue['title']}")
                    
                    response["response"] = f"Recent issues in {owner}/{repo_name}:\n" + "\n".join(issue_list)
                else:
                    response["response"] = "Could not fetch issues or no issues found."
                    
            except (ValueError, IndexError):
                response["response"] = "Please specify repository as 'owner/repo_name'"
        else:
            response["response"] = "Please specify which repository you want to check. Example: 'show issues for repo octocat/hello-world'"
    
    else:
        response["response"] = "I can help you check GitHub issues. Try asking: 'Show issues for repo owner/repo-name'"
    
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)