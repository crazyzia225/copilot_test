from flask import Flask, request, jsonify, render_template
import requests
import os
import json
import time
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

# In-memory storage for notifications (use database in production)
notification_settings = {}
last_checked = {}

class GitHubHandler:
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.token = os.getenv('GITHUB_TOKEN')
    
    def get_headers(self):
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Issues-Bot'
        }
        if self.token:
            headers['Authorization'] = f'token {self.token}'
        return headers

    def get_issues(self, owner, repo, state='open', labels=None, assignee=None, creator=None, per_page=10):
        """Fetch issues with filtering options"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {
            'state': state,
            'per_page': per_page
        }
        
        # Add filters if provided
        if labels:
            params['labels'] = labels
        if assignee:
            params['assignee'] = assignee
        if creator:
            params['creator'] = creator
        
        response = requests.get(url, params=params, headers=self.get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch issues: {response.status_code} - {response.text}"}

    def get_issue(self, owner, repo, issue_number):
        """Get specific issue details"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        response = requests.get(url, headers=self.get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch issue: {response.status_code}"}

    def create_issue(self, owner, repo, title, body, labels=None, assignees=None):
        """Create a new issue"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        
        data = {
            "title": title,
            "body": body
        }
        
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        
        response = requests.post(url, json=data, headers=self.get_headers())
        
        if response.status_code == 201:
            return response.json()
        else:
            return {"error": f"Failed to create issue: {response.status_code} - {response.text}"}

    def update_issue(self, owner, repo, issue_number, title=None, body=None, state=None, labels=None, assignees=None):
        """Update an existing issue"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}"
        
        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
        
        response = requests.patch(url, json=data, headers=self.get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to update issue: {response.status_code}"}

    def add_comment(self, owner, repo, issue_number, comment):
        """Add comment to an issue"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        data = {"body": comment}
        response = requests.post(url, json=data, headers=self.get_headers())
        
        if response.status_code == 201:
            return response.json()
        else:
            return {"error": f"Failed to add comment: {response.status_code}"}

    def get_new_issues_since(self, owner, repo, since_date):
        """Get issues created since a specific date"""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {
            'state': 'all',
            'since': since_date.isoformat(),
            'sort': 'created',
            'direction': 'desc'
        }
        
        response = requests.get(url, params=params, headers=self.get_headers())
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Failed to fetch new issues: {response.status_code}"}

github = GitHubHandler()

def check_for_new_issues():
    """Background task to check for new issues"""
    while True:
        try:
            for user_id, settings in notification_settings.items():
                owner = settings.get('owner')
                repo = settings.get('repo')
                last_check = last_checked.get(user_id, datetime.now() - timedelta(hours=1))
                
                if owner and repo:
                    new_issues = github.get_new_issues_since(owner, repo, last_check)
                    
                    if not isinstance(new_issues, dict) or 'error' not in new_issues:
                        for issue in new_issues:
                            if 'pull_request' not in issue:
                                print(f"🔔 New issue found: #{issue['number']} - {issue['title']}")
                                # In a real application, you'd send this to the user
                                # via websocket, email, or push notification
            time.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Error in notification check: {e}")
            time.sleep(300)

# Start background thread for notifications
notification_thread = threading.Thread(target=check_for_new_issues, daemon=True)
notification_thread.start()

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message', '').lower()
    user_id = request.remote_addr  # Using IP as user identifier
    
    response = process_message(user_message, user_id)
    return jsonify(response)

def process_message(message, user_id):
    """Process user message and return appropriate response"""
    message_lower = message.lower()
    
    # Get issues from repository
    if any(keyword in message_lower for keyword in ['issues', 'show issues', 'get issues']):
        return handle_issues_request(message, user_id)
    
    # Create new issue
    elif any(keyword in message_lower for keyword in ['create issue', 'new issue']):
        return handle_create_issue(message)
    
    # Update issue
    elif any(keyword in message_lower for keyword in ['update issue', 'close issue', 'edit issue']):
        return handle_update_issue(message)
    
    # Add comment to issue
    elif any(keyword in message_lower for keyword in ['add comment', 'comment on']):
        return handle_add_comment(message)
    
    # Setup notifications
    elif any(keyword in message_lower for keyword in ['notify', 'notification', 'alert']):
        return handle_notifications(message, user_id)
    
    # Help command
    elif 'help' in message_lower:
        return get_help_response()
    
    else:
        return {"response": get_help_response()}

def handle_issues_request(message, user_id):
    """Handle requests to get issues with filtering"""
    try:
        # Extract repository info
        if 'repo' in message:
            parts = message.split()
            repo_index = parts.index('repo') + 1
            repo_full = parts[repo_index]
            owner, repo_name = repo_full.split('/')
        else:
            # Default to user's repository
            owner = "crazyzia225"
            repo_name = "copilot_test"
        
        # Extract filters
        labels = None
        assignee = None
        creator = None
        state = 'open'
        
        if 'label' in message:
            labels = extract_parameter(message, 'label')
        if 'assignee' in message:
            assignee = extract_parameter(message, 'assignee')
        if 'creator' in message:
            creator = extract_parameter(message, 'creator')
        if 'closed' in message:
            state = 'closed'
        if 'all' in message:
            state = 'all'
        
        issues = github.get_issues(owner, repo_name, state, labels, assignee, creator)
        
        if isinstance(issues, dict) and 'error' in issues:
            return {"response": f"Error: {issues['error']}"}
        
        if not issues:
            return {"response": "No issues found matching your criteria."}
        
        # Format response with filters info
        filter_info = []
        if labels:
            filter_info.append(f"labels: {labels}")
        if assignee:
            filter_info.append(f"assignee: {assignee}")
        if creator:
            filter_info.append(f"creator: {creator}")
        
        filter_str = f" (filters: {', '.join(filter_info)})" if filter_info else ""
        
        issue_list = []
        for issue in issues[:8]:  # Show first 8 issues
            if 'pull_request' not in issue:
                labels_str = ", ".join([label['name'] for label in issue['labels']]) if issue['labels'] else "none"
                assignee_str = issue['assignee']['login'] if issue['assignee'] else "unassigned"
                
                issue_list.append(
                    f"#{issue['number']}: {issue['title']}\n"
                    f"   State: {issue['state']} | Assignee: {assignee_str}\n"
                    f"   Labels: {labels_str}\n"
                    f"   URL: {issue['html_url']}"
                )
        
        response = f"📋 Issues in {owner}/{repo_name}{filter_str}:\n\n" + "\n\n".join(issue_list)
        return {"response": response}
        
    except Exception as e:
        return {"response": f"Error processing your request: {str(e)}"}

def handle_create_issue(message):
    """Handle creating new issues"""
    try:
        # Extract repository
        if 'repo' in message:
            repo_part = message.split('repo')[1].split()[0]
            owner, repo_name = repo_part.split('/')
        else:
            owner = "crazyzia225"
            repo_name = "copilot_test"
        
        # Extract title and body (simple parsing)
        if 'title:' in message and 'body:' in message:
            title = message.split('title:')[1].split('body:')[0].strip()
            body = message.split('body:')[1].strip()
        else:
            # Fallback parsing
            parts = message.split('|')
            if len(parts) >= 2:
                title = parts[0].replace('create issue', '').replace('in', '').strip()
                body = parts[1].strip()
            else:
                return {"response": "Please provide both title and body separated by '|'. Example: 'create issue in owner/repo: Bug fix | This is a bug description'"}
        
        result = github.create_issue(owner, repo_name, title, body)
        
        if isinstance(result, dict) and 'error' in result:
            return {"response": f"Failed to create issue: {result['error']}"}
        
        return {"response": f"✅ Issue created successfully!\n#{result['number']}: {result['title']}\nURL: {result['html_url']}"}
        
    except Exception as e:
        return {"response": f"Error creating issue: {str(e)}"}

def handle_update_issue(message):
    """Handle updating issues"""
    try:
        # Extract issue number
        if '#' in message:
            issue_num = message.split('#')[1].split()[0]
        else:
            return {"response": "Please specify issue number with #. Example: 'close issue #1 in owner/repo'"}
        
        # Extract repository
        if 'repo' in message:
            repo_part = message.split('repo')[1].split()[0]
            owner, repo_name = repo_part.split('/')
        else:
            owner = "crazyzia225"
            repo_name = "copilot_test"
        
        # Determine update type
        if 'close' in message:
            result = github.update_issue(owner, repo_name, issue_num, state='closed')
            action = "closed"
        elif 'reopen' in message:
            result = github.update_issue(owner, repo_name, issue_num, state='open')
            action = "reopened"
        else:
            return {"response": "Please specify action: 'close issue #1' or 'reopen issue #1'"}
        
        if isinstance(result, dict) and 'error' in result:
            return {"response": f"Failed to update issue: {result['error']}"}
        
        return {"response": f"✅ Issue #{issue_num} {action} successfully!"}
        
    except Exception as e:
        return {"response": f"Error updating issue: {str(e)}"}

def handle_add_comment(message):
    """Handle adding comments to issues"""
    try:
        # Extract issue number
        if '#' in message:
            issue_num = message.split('#')[1].split()[0]
        else:
            return {"response": "Please specify issue number with #. Example: 'add comment on #1: This is a comment'"}
        
        # Extract repository
        if 'repo' in message:
            repo_part = message.split('repo')[1].split()[0]
            owner, repo_name = repo_part.split('/')
        else:
            owner = "crazyzia225"
            repo_name = "copilot_test"
        
        # Extract comment
        if ':' in message:
            comment = message.split(':')[1].strip()
        else:
            return {"response": "Please provide comment after ':'. Example: 'add comment on #1: This is my comment'"}
        
        result = github.add_comment(owner, repo_name, issue_num, comment)
        
        if isinstance(result, dict) and 'error' in result:
            return {"response": f"Failed to add comment: {result['error']}"}
        
        return {"response": f"💬 Comment added to issue #{issue_num}!"}
        
    except Exception as e:
        return {"response": f"Error adding comment: {str(e)}"}

def handle_notifications(message, user_id):
    """Handle notification setup"""
    try:
        if 'setup' in message or 'start' in message:
            # Extract repository
            if 'repo' in message:
                repo_part = message.split('repo')[1].split()[0]
                owner, repo_name = repo_part.split('/')
            else:
                owner = "crazyzia225"
                repo_name = "copilot_test"
            
            notification_settings[user_id] = {
                'owner': owner,
                'repo': repo_name,
                'enabled': True
            }
            last_checked[user_id] = datetime.now()
            
            return {"response": f"🔔 Notifications enabled for {owner}/{repo_name}! I'll check for new issues every 5 minutes."}
        
        elif 'stop' in message or 'disable' in message:
            if user_id in notification_settings:
                notification_settings[user_id]['enabled'] = False
                return {"response": "🔕 Notifications disabled."}
            else:
                return {"response": "No active notifications to disable."}
        
        else:
            return {"response": "Use 'setup notifications for repo owner/repo' to enable notifications."}
            
    except Exception as e:
        return {"response": f"Error setting up notifications: {str(e)}"}

def extract_parameter(message, param_name):
    """Extract parameters like labels, assignee from message"""
    try:
        if f"{param_name}:" in message:
            return message.split(f"{param_name}:")[1].split()[0]
        return None
    except:
        return None

def get_help_response():
    """Return help message with all available commands"""
    return """🤖 **GitHub Issues Bot Help**

**View Issues:**
• `show issues for repo owner/repo` - Get issues
• `show closed issues for repo owner/repo` - Get closed issues
• `show issues with label:bug` - Filter by label
• `show issues with assignee:username` - Filter by assignee
• `show issues with creator:username` - Filter by creator

**Manage Issues:**
• `create issue in owner/repo: Title | Description` - Create new issue
• `close issue #1 in owner/repo` - Close an issue
• `reopen issue #1 in owner/repo` - Reopen an issue
• `add comment on #1: Your comment` - Add comment to issue

**Notifications:**
• `setup notifications for repo owner/repo` - Get alerts for new issues
• `stop notifications` - Disable notifications

**Example:**
`show issues for repo crazyzia225/copilot_test with label:bug`
`create issue in crazyzia225/copilot_test: Bug Fix | This is a bug description`"""

if __name__ == '__main__':
    app.run(debug=True)