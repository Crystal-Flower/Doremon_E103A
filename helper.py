import json
from typing import List, Dict


def load_json(path: str) -> Dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_user_slack_messages(slack_data: Dict, user_id: str) -> List[Dict]:
    """
    Extract all Slack messages authored by a specific user
    """
    user_messages = []

    for channel in slack_data.get("channels", []):
        for msg in channel.get("messages", []):
            if msg.get("user") == user_id:
                user_messages.append({
                    "channel": channel["channel_id"],
                    "timestamp": msg["ts"],
                    "text": msg["text"],
                    "contains_code": msg.get("contains_code", False)
                })

    return user_messages


def get_user_github_commits(github_data: Dict, user_id: str) -> List[Dict]:
    """
    Extract all GitHub commits authored by a specific user
    """
    return [
        {
            "sha": commit["sha"],
            "date": commit["date"],
            "message": commit["commit_message"],
            "files_changed": commit["files_changed"],
            "lines_added": commit["lines_added"],
            "lines_deleted": commit["lines_deleted"],
            "area": commit["area"],
            "codediff": commit["codediff"]
        }
        for commit in github_data.get("commits", [])
        if commit.get("author") == user_id
    ]


def get_user_received_code(slack_data: Dict, user_id: str) -> List[Dict]:
    """
    Detect code snippets shared BY OTHERS in conversations involving the user
    """
    received_code = []

    for channel in slack_data.get("channels", []):
        messages = channel.get("messages", [])
        for i, msg in enumerate(messages):
            # Code shared by someone else
            if msg.get("contains_code") and msg.get("user") != user_id:
                # Check if user replied after (simple heuristic)
                for follow_up in messages[i + 1:i + 4]:
                    if follow_up.get("user") == user_id:
                        received_code.append({
                            "channel": channel["channel_id"],
                            "from_user": msg["user"],
                            "code_snippet": msg["text"],
                            "acknowledged_by_user": follow_up["text"]
                        })
                        break

    return received_code


def get_user_meeting_transcripts_with_context(
    transcripts_data,
    user_id,
    context_window=2
):
    """
    Extract meeting transcript flows where the user participates,
    including surrounding context lines.
    """
    results = []

    for meeting in transcripts_data:
        meeting_id = meeting.get("meeting_id")
        transcript = meeting.get("transcript", [])
        included_indices = set()

        for idx, line in enumerate(transcript):
            if line.get("user") == user_id:
                start = max(0, idx - context_window)
                end = min(len(transcript), idx + context_window + 1)

                for i in range(start, end):
                    included_indices.add(i)

        if included_indices:
            flow = []
            for i in sorted(included_indices):
                flow.append({
                    "user": transcript[i]["user"],
                    "text": transcript[i]["text"]
                })

            results.append({
                "meeting_id": meeting_id,
                "flow": flow
            })

    return results


def extract_peer_kudos(slack_data, github_data, user_id, context_window=3):
    """
    Detect peer kudos: code shared by user, acknowledged or used by teammates
    """
    kudos = []

    for channel in slack_data.get("channels", []):
        messages = channel.get("messages", [])
        for idx, msg in enumerate(messages):
            # Code shared by target user
            if msg.get("user") == user_id and msg.get("contains_code", False):
                code_snippet = msg["text"]

                # Check next few messages for acknowledgment by others
                for follow_up in messages[idx + 1 : idx + 1 + context_window]:
                    if follow_up["user"] != user_id:
                        kudos.append({
                            "from_user": user_id,
                            "to_user": follow_up["user"],
                            "channel": channel["channel_id"],
                            "code_snippet": code_snippet,
                            "ack_text": follow_up["text"],
                            "type": "slack_ack"
                        })

                # Optionally: Check GitHub commits for usage
                for commit in github_data.get("commits", []):
                    if commit.get("author") != user_id:
                        commit_text = commit.get("codediff", "") + " " + commit.get("commit_message", "")
                        if code_snippet[:30] in commit_text:  # simple heuristic
                            kudos.append({
                                "from_user": user_id,
                                "to_user": commit["author"],
                                "channel": "github",
                                "code_snippet": code_snippet,
                                "commit_sha": commit["sha"],
                                "type": "github_usage"
                            })

    return kudos