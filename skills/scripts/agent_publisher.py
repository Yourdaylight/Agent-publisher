#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Agent Publisher CLI — OpenClaw Skill Script

A self-contained CLI that wraps every Agent Publisher Skills API endpoint.
The agent only needs an email (whitelisted) to authenticate and operate.

Usage:
    uv run agent_publisher.py <command> [options]

Commands:
    auth            Authenticate with email, obtain a skill token
    whoami          Show current identity
    accounts        List your WeChat official accounts
    accounts-all    List ALL accounts (admin only)
    create-account  Bind a new WeChat official account
    agents          List agents (optionally filter by account)
    create-agent    Create a content agent for an account
    generate        Trigger article generation for an agent
    task            Check task status
    articles        List articles
    article         Get article detail
    create-article  Create an article manually with custom content
    edit-article    Edit an existing article's fields
    sync-article    Sync article edits to WeChat draft box
    publish         Publish a single article to WeChat draft
    batch-publish   Batch publish articles (admin only)
    media           List media assets in the library
    upload-media    Upload an image/file to the media library
    delete-media    Delete a media asset
    followers       View follower statistics for an account
    article-stats   View article statistics for an account
    list-styles     List all style presets (with full prompt)
    edit-style      Edit a style preset's name/description/prompt
    create-style    Create a custom style preset
    delete-style    Delete a custom style preset
    generate-variants  Generate variant articles from a source
    variant-status  Check batch variant generation task status
    variants        List variant articles for a source article
    update-agent    Update an agent's configuration (incl. binding style)
    list-admins     List all admin emails (admin only)
    add-admin       Add a runtime admin (admin only)
    remove-admin    Remove a runtime admin (admin only)

Environment:
    AP_URL          Agent Publisher backend URL (default: http://localhost:9099)
    AP_TOKEN        Skill token (from 'auth' command). Can also use --token.
    AP_EMAIL        Email for auto-auth. Can also use --email.
"""

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_URL = "http://localhost:9099"
TOKEN_FILE = os.path.expanduser("~/.agent-publisher-token")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_base_url(args):
    """Resolve the backend URL from args or environment."""
    return (getattr(args, "url", None) or os.environ.get("AP_URL") or DEFAULT_URL).rstrip("/")


def save_token(token, email):
    """Persist token locally for subsequent commands."""
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "email": email, "ts": int(time.time())}, f)
    os.chmod(TOKEN_FILE, 0o600)


def load_token():
    """Load persisted token."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def resolve_token(args):
    """Get the skill token from --token, env, or saved file."""
    token = getattr(args, "token", None) or os.environ.get("AP_TOKEN")
    if token:
        return token
    saved = load_token()
    if saved:
        return saved.get("token")
    return None


def api(method, url, token=None, **kwargs):
    """Make an HTTP request and return parsed JSON or exit on error."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # Only set JSON content-type when sending JSON body
    if "json" in kwargs:
        headers.setdefault("Content-Type", "application/json")

    try:
        resp = httpx.request(method, url, headers=headers, timeout=60, **kwargs)
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {url}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code >= 400:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    return resp.text


def require_token(args):
    """Ensure we have a valid token, auto-auth if email is available."""
    token = resolve_token(args)
    if token:
        return token

    # Try auto-auth with email
    email = getattr(args, "email", None) or os.environ.get("AP_EMAIL")
    if email:
        base = get_base_url(args)
        result = api("POST", f"{base}/api/skills/auth", json={"email": email})
        save_token(result["token"], result["email"])
        return result["token"]

    print('Error: No token found. Run "auth" first or provide --email / AP_EMAIL.', file=sys.stderr)
    sys.exit(1)


def pp(data):
    """Pretty-print JSON data."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_auth(args):
    """Authenticate with email and save the token."""
    base = get_base_url(args)
    email = args.email or os.environ.get("AP_EMAIL")
    if not email:
        print("Error: --email is required for auth.", file=sys.stderr)
        sys.exit(1)

    result = api("POST", f"{base}/api/skills/auth", json={"email": email})
    save_token(result["token"], result["email"])
    print(f"✅ Authenticated as {result['email']} (admin={result['is_admin']})")
    print(f"Token saved to {TOKEN_FILE}")
    if args.show_token:
        print(f"Token: {result['token']}")


def cmd_whoami(args):
    """Show current identity."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/whoami", token=token)
    pp(result)


def cmd_accounts(args):
    """List own WeChat accounts."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/accounts", token=token)
    if not result:
        print('No accounts found. Use "create-account" to add one.')
        return
    for acc in result:
        print(
            f"  [{acc['id']}] {acc['name']}  appid={acc['appid']}  owner={acc.get('owner_email', 'N/A')}"
        )


def cmd_accounts_all(args):
    """List ALL accounts (admin only)."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/accounts/all", token=token)
    if not result:
        print("No accounts in the system.")
        return
    for acc in result:
        print(
            f"  [{acc['id']}] {acc['name']}  appid={acc['appid']}  owner={acc.get('owner_email', 'N/A')}"
        )


def cmd_create_account(args):
    """Create (bind) a new WeChat official account."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {
        "name": args.name,
        "appid": args.appid,
        "appsecret": args.appsecret,
    }
    result = api("POST", f"{base}/api/skills/accounts", token=token, json=payload)
    print(
        f"✅ Account created: id={result['id']} name={result['name']} owner={result.get('owner_email')}"
    )


def cmd_agents(args):
    """List agents (uses the standard /api/agents endpoint via skill token)."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/agents", token=token)
    if not result:
        print('No agents found. Use "create-agent" to add one.')
        return
    for ag in result:
        status = "🟢" if ag.get("is_active") else "🔴"
        style = ag.get("default_style_id") or "-"
        print(
            f"  {status} [{ag['id']}] {ag['name']}  topic={ag['topic']}  account_id={ag['account_id']}  style={style}  cron={ag.get('schedule_cron', 'N/A')}"
        )


def cmd_create_agent(args):
    """Create a content agent for a specific account."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {
        "name": args.name,
        "topic": args.topic,
        "account_id": args.account_id,
        "schedule_cron": args.cron,
    }
    if args.description:
        payload["description"] = args.description
    if args.rss:
        payload["rss_sources"] = [
            {"name": r.split("=")[0], "url": r.split("=")[1]} for r in args.rss
        ]
    if args.image_style:
        payload["image_style"] = args.image_style
    if args.default_style:
        payload["default_style_id"] = args.default_style
    result = api("POST", f"{base}/api/skills/agents", token=token, json=payload)
    print(f"\u2705 Agent created: id={result['id']} name={result['name']} topic={result['topic']}")


def cmd_update_agent(args):
    """Update an agent's configuration."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.topic:
        payload["topic"] = args.topic
    if args.description:
        payload["description"] = args.description
    if args.image_style:
        payload["image_style"] = args.image_style
    if args.default_style is not None:
        # Allow empty string to clear the binding
        payload["default_style_id"] = args.default_style if args.default_style else None
    if args.cron:
        payload["schedule_cron"] = args.cron
    if args.active is not None:
        payload["is_active"] = args.active
    if not payload:
        print("Error: Specify at least one field to update.", file=sys.stderr)
        sys.exit(1)
    result = api("PUT", f"{base}/api/skills/agents/{args.agent_id}", token=token, json=payload)
    print(
        f"\u2705 Agent {result['id']} updated: name={result.get('name')} style={result.get('default_style_id', '-')}"
    )


def cmd_generate(args):
    """Trigger article generation for an agent."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/agents/{args.agent_id}/generate", token=token)
    task_id = result.get("task_id")
    print(f"🚀 Generation started: task_id={task_id} status={result.get('status')}")

    if args.wait:
        print("Waiting for task to complete...")
        for _ in range(60):
            time.sleep(5)
            task = api("GET", f"{base}/api/skills/tasks/{task_id}", token=token)
            status = task.get("status", "")
            steps = task.get("steps", [])
            if steps:
                print(f"  [{status}] steps: {len(steps)}")
            if status in ("success", "failed"):
                print(f"\n{'✅ Done!' if status == 'success' else '❌ Failed!'}")
                if task.get("result"):
                    pp(task["result"])
                return
        print("⏱️  Timeout. Check task status manually.")


def cmd_task(args):
    """Check task status."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/tasks/{args.task_id}", token=token)
    pp(result)


def cmd_articles(args):
    """List articles."""
    base = get_base_url(args)
    token = require_token(args)
    params = {}
    if args.status:
        params["status"] = args.status
    url = f"{base}/api/skills/articles"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    result = api("GET", url, token=token)
    if not result:
        print("No articles found.")
        return
    for art in result:
        print(
            f"  [{art['id']}] {art.get('title', 'Untitled')}  status={art.get('status')}  agent_id={art.get('agent_id')}"
        )


def cmd_article(args):
    """Get article detail."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/articles/{args.article_id}", token=token)
    pp(result)


def cmd_publish(args):
    """Publish a single article to WeChat draft box."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/publish", token=token)
    if result.get("ok"):
        print(f"✅ Published! media_id={result.get('media_id')}")
    else:
        print(f"❌ Failed: {result}")


def cmd_create_article(args):
    """Create an article manually with custom content."""
    base = get_base_url(args)
    token = require_token(args)

    # Read content from file or string
    content = ""
    html_content = ""
    if args.content_file:
        import os.path

        if not os.path.isfile(args.content_file):
            print(f"Error: File not found: {args.content_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.content_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        if args.content_file.endswith(".html") or args.content_file.endswith(".htm"):
            html_content = file_content
        else:
            content = file_content
    elif args.content:
        content = args.content

    # Resolve cover image: if user passes media_id as integer, prefix with media:
    cover = args.cover or ""
    if cover and cover.isdigit():
        cover = f"media:{cover}"

    payload = {
        "agent_id": args.agent_id,
        "title": args.title,
        "digest": args.digest or "",
        "content": content,
        "html_content": html_content,
        "cover_image_url": cover,
        "status": "draft",
    }
    result = api("POST", f"{base}/api/skills/articles", token=token, json=payload)
    print(
        f"✅ Article created: id={result['id']} title={result['title']} status={result['status']}"
    )
    if result.get("cover_image_url"):
        print(f"   Cover: {result['cover_image_url']}")


def cmd_edit_article(args):
    """Edit an existing article's fields."""
    base = get_base_url(args)
    token = require_token(args)

    payload = {}
    if args.title:
        payload["title"] = args.title
    if args.digest:
        payload["digest"] = args.digest

    # Read content from file or string
    if args.content_file:
        import os.path

        if not os.path.isfile(args.content_file):
            print(f"Error: File not found: {args.content_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.content_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        if args.content_file.endswith(".html") or args.content_file.endswith(".htm"):
            payload["html_content"] = file_content
        else:
            payload["content"] = file_content
    elif args.content:
        payload["content"] = args.content

    if args.cover:
        cover = args.cover
        if cover.isdigit():
            cover = f"media:{cover}"
        payload["cover_image_url"] = cover

    if not payload:
        print(
            "Error: No fields specified to update. Use --title, --digest, --content, --content-file, or --cover.",
            file=sys.stderr,
        )
        sys.exit(1)

    result = api("PUT", f"{base}/api/skills/articles/{args.article_id}", token=token, json=payload)
    print(f"✅ Article {result['id']} updated: title={result['title']} status={result['status']}")


def cmd_sync_article(args):
    """Sync article edits to WeChat draft box."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/sync", token=token)
    sync_status = result.get("sync_status", "unknown")
    if result.get("ok"):
        if sync_status == "synced":
            print(f"✅ Article {args.article_id} synced to WeChat draft box.")
        elif sync_status == "skipped":
            print(f"⏭️  Article {args.article_id} skipped (not published or no media_id).")
        else:
            print(f"ℹ️  Sync status: {sync_status}")
    else:
        print(f"❌ Sync failed: {result}")


def cmd_batch_publish(args):
    """Batch publish articles (admin only)."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {"article_ids": args.article_ids}
    result = api("POST", f"{base}/api/skills/articles/batch-publish", token=token, json=payload)
    for r in result:
        status = "✅" if r.get("success") else "❌"
        msg = r.get("media_id") or r.get("error", "")
        print(f"  {status} article {r['article_id']}: {msg}")


def cmd_media(args):
    """List media assets."""
    base = get_base_url(args)
    token = require_token(args)
    params = []
    if args.tag:
        params.append(f"tag={args.tag}")
    if args.page:
        params.append(f"page={args.page}")
    url = f"{base}/api/skills/media"
    if params:
        url += "?" + "&".join(params)
    result = api("GET", url, token=token)
    if not result:
        print('No media assets found. Use "upload-media" to add one.')
        return
    for m in result:
        size_kb = m.get("file_size", 0) / 1024
        tags = ", ".join(m.get("tags", [])) or "-"
        print(
            f"  [{m['id']}] {m['filename']}  {size_kb:.1f}KB  type={m['content_type']}  tags=[{tags}]  url={m.get('url')}"
        )


def cmd_upload_media(args):
    """Upload a file to the media library."""
    import os.path

    base = get_base_url(args)
    token = require_token(args)
    file_path = args.file

    if not os.path.isfile(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_content = f.read()

    # Use multipart upload
    headers = {"Authorization": f"Bearer {token}"}
    files = {"file": (filename, file_content)}
    data = {}
    if args.tags:
        data["tags"] = args.tags
    if args.description:
        data["description"] = args.description

    try:
        resp = httpx.post(
            f"{base}/api/skills/media",
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {base}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code >= 400:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    result = resp.json()
    print(
        f"✅ Uploaded: id={result['id']} filename={result['filename']} size={result['file_size']}"
    )
    print(f"   URL: {base}{result.get('url', '')}")
    if result.get("tags"):
        print(f"   Tags: {', '.join(result['tags'])}")


def cmd_delete_media(args):
    """Delete a media asset."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("DELETE", f"{base}/api/skills/media/{args.media_id}", token=token)
    if result.get("ok"):
        print(f"\u2705 Deleted media asset {args.media_id}")
    else:
        print(f"\u274c Failed: {result}")


def cmd_followers(args):
    """View follower statistics for an account."""
    base = get_base_url(args)
    token = require_token(args)

    params = []
    if args.begin_date:
        params.append(f"begin_date={args.begin_date}")
    if args.end_date:
        params.append(f"end_date={args.end_date}")

    url = f"{base}/api/skills/accounts/{args.account_id}/followers"
    if params:
        url += "?" + "&".join(params)

    result = api("GET", url, token=token)

    print(
        f"\n\U0001f4ca Followers for [{result.get('account_name', 'N/A')}] (account_id={result.get('account_id')})"
    )
    print(f"   Period: {result.get('begin_date')} ~ {result.get('end_date')}")
    print(f"   Total followers: {result.get('total_followers', 'N/A')}")

    user_summary = result.get("user_summary", [])
    if user_summary:
        print(f"\n   {'Date':<12} {'New':>8} {'Cancel':>8} {'Net':>8}")
        print(f"   {'-' * 12} {'-' * 8} {'-' * 8} {'-' * 8}")
        for item in user_summary:
            ref_date = item.get("ref_date", "N/A")
            new_user = item.get("new_user", 0)
            cancel_user = item.get("cancel_user", 0)
            net = new_user - cancel_user
            print(f"   {ref_date:<12} {new_user:>8} {cancel_user:>8} {net:>+8}")

    user_cumulate = result.get("user_cumulate", [])
    if user_cumulate:
        print(f"\n   {'Date':<12} {'Cumulate':>10}")
        print(f"   {'-' * 12} {'-' * 10}")
        for item in user_cumulate:
            ref_date = item.get("ref_date", "N/A")
            cumulate = item.get("cumulate_user", 0)
            print(f"   {ref_date:<12} {cumulate:>10}")

    if not user_summary and not user_cumulate:
        print("\n   No data available for the specified period.")

    warnings = result.get("warnings", [])
    for w in warnings:
        print(f"\n   ⚠️  {w}")


def cmd_article_stats(args):
    """View article statistics for an account."""
    base = get_base_url(args)
    token = require_token(args)

    params = []
    if args.begin_date:
        params.append(f"begin_date={args.begin_date}")
    if args.end_date:
        params.append(f"end_date={args.end_date}")

    url = f"{base}/api/skills/accounts/{args.account_id}/article-stats"
    if params:
        url += "?" + "&".join(params)

    result = api("GET", url, token=token)

    print(
        f"\n\U0001f4c8 Article Stats for [{result.get('account_name', 'N/A')}] (account_id={result.get('account_id')})"
    )
    print(f"   Period: {result.get('begin_date')} ~ {result.get('end_date')}")

    article_summary = result.get("article_summary", [])
    if article_summary:
        print("\n   Daily Summary:")
        print(f"   {'Date':<12} {'Reads':>8} {'Shares':>8} {'Favorites':>10}")
        print(f"   {'-' * 12} {'-' * 8} {'-' * 8} {'-' * 10}")
        for item in article_summary:
            ref_date = item.get("ref_date", "N/A")
            int_page_read_count = item.get("int_page_read_count", 0)
            share_count = item.get("share_count", 0)
            add_to_fav_count = item.get("add_to_fav_count", 0)
            print(
                f"   {ref_date:<12} {int_page_read_count:>8} {share_count:>8} {add_to_fav_count:>10}"
            )

    article_total = result.get("article_total", [])
    if article_total:
        print("\n   Per-Article Detail:")
        print(
            f"   {'Date':<12} {'Title':<30} {'Read(U)':>8} {'Read(C)':>8} {'Share(U)':>9} {'Fav(U)':>7}"
        )
        print(f"   {'-' * 12} {'-' * 30} {'-' * 8} {'-' * 8} {'-' * 9} {'-' * 7}")
        for item in article_total:
            ref_date = item.get("ref_date", "N/A")
            title = item.get("title", "N/A")
            if len(title) > 28:
                title = title[:28] + ".."
            details_list = item.get("details", [])
            if details_list:
                for detail in details_list:
                    stat = detail.get("stat_date", ref_date)
                    read_user = detail.get("int_page_read_user", 0)
                    read_count = detail.get("int_page_read_count", 0)
                    share_user = detail.get("share_user", 0)
                    fav_user = detail.get("add_to_fav_user", 0)
                    print(
                        f"   {stat:<12} {title:<30} {read_user:>8} {read_count:>8} {share_user:>9} {fav_user:>7}"
                    )
            else:
                print(f"   {ref_date:<12} {title:<30} {'--':>8} {'--':>8} {'--':>9} {'--':>7}")

    if not article_summary and not article_total:
        print("\n   No article data available for the specified period.")

    warnings = result.get("warnings", [])
    for w in warnings:
        print(f"\n   ⚠️  {w}")


def cmd_list_admins(args):
    """List all admin emails."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/admins", token=token)
    print("\n📋 Admin List:")
    env_admins = result.get("env_admins", [])
    runtime_admins = result.get("runtime_admins", [])
    all_admins = result.get("all_admins", [])
    if env_admins:
        print("  Env-configured:")
        for e in env_admins:
            print(f"    • {e}")
    if runtime_admins:
        print("  Runtime-added:")
        for e in runtime_admins:
            print(f"    • {e}")
    if not all_admins:
        print("  (no admins configured)")
    else:
        print(f"\n  Total: {len(all_admins)} admin(s)")


def cmd_add_admin(args):
    """Add a runtime admin."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/admins", token=token, json={"email": args.admin_email})
    if result.get("ok"):
        print(f"✅ {result.get('message', 'Admin added')}")
    else:
        print(f"❌ {result}")


def cmd_remove_admin(args):
    """Remove a runtime admin."""
    base = get_base_url(args)
    token = require_token(args)
    result = api(
        "DELETE", f"{base}/api/skills/admins", token=token, json={"email": args.admin_email}
    )
    if result.get("ok"):
        print(f"\u2705 {result.get('message', 'Admin removed')}")
    else:
        print(f"\u274c {result}")


# ---------------------------------------------------------------------------
# Style Preset Commands
# ---------------------------------------------------------------------------


def cmd_list_styles(args):
    """List all style presets with full prompt content."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/style-presets", token=token)
    if not result:
        print("No style presets found.")
        return
    for s in result:
        builtin = " [builtin]" if s.get("is_builtin") else " [custom]"
        print(f"\n  [{s['style_id']}] {s['name']}{builtin}")
        print(f"    Description: {s.get('description', '-')}")
        prompt = s.get("prompt", "")
        # Show first 200 chars of prompt
        if len(prompt) > 200:
            print(f"    Prompt: {prompt[:200]}...")
        else:
            print(f"    Prompt: {prompt}")
    if args.full:
        print("\n--- Full prompt content ---")
        for s in result:
            print(f"\n=== {s['style_id']} ({s['name']}) ===")
            print(s.get("prompt", "(empty)"))


def cmd_edit_style(args):
    """Edit a style preset's name, description, or prompt."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.description:
        payload["description"] = args.description
    if args.prompt:
        payload["prompt"] = args.prompt
    if args.prompt_file:
        import os.path

        if not os.path.isfile(args.prompt_file):
            print(f"Error: File not found: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            payload["prompt"] = f.read()
    if not payload:
        print(
            "Error: Specify at least one field: --name, --description, --prompt, or --prompt-file.",
            file=sys.stderr,
        )
        sys.exit(1)
    result = api(
        "PUT", f"{base}/api/skills/style-presets/{args.style_id}", token=token, json=payload
    )
    print(f"\u2705 Style '{result.get('style_id')}' updated: {result.get('name')}")


def cmd_create_style(args):
    """Create a custom style preset."""
    base = get_base_url(args)
    token = require_token(args)
    payload = {
        "style_id": args.style_id,
        "name": args.name,
        "description": args.description or "",
        "prompt": args.prompt or "",
    }
    if args.prompt_file:
        import os.path

        if not os.path.isfile(args.prompt_file):
            print(f"Error: File not found: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            payload["prompt"] = f.read()
    result = api("POST", f"{base}/api/skills/style-presets", token=token, json=payload)
    print(f"\u2705 Style created: {result.get('style_id')} ({result.get('name')})")


def cmd_delete_style(args):
    """Delete a custom style preset (built-in presets cannot be deleted)."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("DELETE", f"{base}/api/skills/style-presets/{args.style_id}", token=token)
    if isinstance(result, dict) and result.get("ok"):
        print(f"\u2705 Style {args.style_id} deleted.")
    else:
        print(f"\u2705 Style {args.style_id} deleted.")


# ---------------------------------------------------------------------------
# Variant Commands
# ---------------------------------------------------------------------------


def cmd_generate_variants(args):
    """Generate variant articles from a source article."""
    base = get_base_url(args)
    token = require_token(args)
    agent_ids = [int(x.strip()) for x in args.agents.split(",")]
    style_ids = [x.strip() for x in args.styles.split(",")]
    payload = {"agent_ids": agent_ids, "style_ids": style_ids}
    result = api(
        "POST", f"{base}/api/skills/articles/{args.article_id}/variants", token=token, json=payload
    )
    if result.get("ok"):
        print(
            f"\U0001f680 Variant generation started: batch_task_id={result.get('batch_task_id')} total={result.get('total')}"
        )
    else:
        print(f"\u274c Failed: {result}")

    if args.wait and result.get("batch_task_id"):
        task_id = result["batch_task_id"]
        print("Waiting for task to complete...")
        for _ in range(120):
            time.sleep(5)
            task = api("GET", f"{base}/api/skills/tasks/{task_id}", token=token)
            status = task.get("status", "")
            task_result = task.get("result", {})
            completed = task_result.get("completed", 0)
            total = task_result.get("total", 0)
            print(f"  [{status}] {completed}/{total} completed")
            if status in ("completed", "partial_completed", "failed"):
                succeeded = task_result.get("succeeded", 0)
                failed = task_result.get("failed", 0)
                emoji = "\u2705" if status == "completed" else "\u26a0\ufe0f"
                print(f"\n{emoji} Done! succeeded={succeeded} failed={failed}")
                subtasks = task_result.get("subtasks", [])
                for st in subtasks:
                    st_emoji = "\u2705" if st.get("status") == "success" else "\u274c"
                    article_info = (
                        f" article_id={st.get('article_id')}" if st.get("article_id") else ""
                    )
                    error_info = f" error={st.get('error')}" if st.get("error") else ""
                    print(
                        f"  {st_emoji} agent={st.get('agent_id')} style={st.get('style_id')}{article_info}{error_info}"
                    )
                return
        print("\u23f1\ufe0f  Timeout. Check task status manually.")


def cmd_variant_status(args):
    """Check batch variant generation task status."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/tasks/{args.batch_task_id}", token=token)
    pp(result)


def cmd_variants(args):
    """List variant articles for a source article."""
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/articles/{args.article_id}/variants", token=token)
    if not result:
        print("No variants found for this article.")
        return
    for v in result:
        print(
            f"  [{v['id']}] {v.get('title', 'Untitled')}  style={v.get('variant_style', '-')}  agent={v.get('agent_name', v.get('agent_id'))}  status={v.get('status')}"
        )


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent_publisher",
        description="Agent Publisher CLI — OpenClaw Skill Script",
    )
    parser.add_argument("--url", help=f"Backend URL (default: {DEFAULT_URL}, env: AP_URL)")
    parser.add_argument("--token", help="Skill token (env: AP_TOKEN)")
    parser.add_argument("--email", help="Email for auto-auth (env: AP_EMAIL)")

    sub = parser.add_subparsers(dest="command", required=True)

    # auth
    p = sub.add_parser("auth", help="Authenticate with email")
    p.add_argument("--email", "-e", dest="email", help="Your whitelisted email")
    p.add_argument("--show-token", action="store_true", help="Print token to stdout")
    p.set_defaults(func=cmd_auth)

    # whoami
    p = sub.add_parser("whoami", help="Show current identity")
    p.set_defaults(func=cmd_whoami)

    # accounts
    p = sub.add_parser("accounts", help="List your WeChat accounts")
    p.set_defaults(func=cmd_accounts)

    # accounts-all
    p = sub.add_parser("accounts-all", help="List ALL accounts (admin)")
    p.set_defaults(func=cmd_accounts_all)

    # create-account
    p = sub.add_parser("create-account", help="Bind a new WeChat account")
    p.add_argument("--name", "-n", required=True, help="Account display name")
    p.add_argument("--appid", required=True, help="WeChat AppID")
    p.add_argument("--appsecret", required=True, help="WeChat AppSecret")
    p.set_defaults(func=cmd_create_account)

    # agents
    p = sub.add_parser("agents", help="List agents")
    p.set_defaults(func=cmd_agents)

    # create-agent
    p = sub.add_parser("create-agent", help="Create a content agent")
    p.add_argument("--name", "-n", required=True, help="Agent name")
    p.add_argument("--topic", "-t", required=True, help="Content topic")
    p.add_argument("--account-id", type=int, required=True, help="Target account ID")
    p.add_argument("--cron", default="0 8 * * *", help="Schedule cron (default: daily 8am)")
    p.add_argument("--description", help="Agent description")
    p.add_argument("--rss", action="append", help="RSS source name=url (repeatable)")
    p.add_argument("--image-style", help="Image generation style")
    p.add_argument("--default-style", help="Default variant style preset ID (e.g. tech, uncle)")
    p.set_defaults(func=cmd_create_agent)

    # update-agent
    p = sub.add_parser("update-agent", help="Update an agent config (incl. binding style)")
    p.add_argument("agent_id", type=int, help="Agent ID")
    p.add_argument("--name", help="New agent name")
    p.add_argument("--topic", help="New content topic")
    p.add_argument("--description", help="New description")
    p.add_argument("--image-style", help="New image generation style")
    p.add_argument(
        "--default-style", help="Default variant style preset ID (empty string to clear)"
    )
    p.add_argument("--cron", help="New schedule cron")
    p.add_argument(
        "--active",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        help="Active status (true/false)",
    )
    p.set_defaults(func=cmd_update_agent)

    # generate
    p = sub.add_parser("generate", help="Trigger article generation")
    p.add_argument("agent_id", type=int, help="Agent ID")
    p.add_argument("--wait", "-w", action="store_true", help="Wait for completion")
    p.set_defaults(func=cmd_generate)

    # task
    p = sub.add_parser("task", help="Check task status")
    p.add_argument("task_id", type=int, help="Task ID")
    p.set_defaults(func=cmd_task)

    # articles
    p = sub.add_parser("articles", help="List articles")
    p.add_argument("--status", help="Filter by status (draft/published)")
    p.set_defaults(func=cmd_articles)

    # article
    p = sub.add_parser("article", help="Get article detail")
    p.add_argument("article_id", type=int, help="Article ID")
    p.set_defaults(func=cmd_article)

    # publish
    p = sub.add_parser("publish", help="Publish article to WeChat draft")
    p.add_argument("article_id", type=int, help="Article ID")
    p.set_defaults(func=cmd_publish)

    # create-article
    p = sub.add_parser("create-article", help="Create article with custom content")
    p.add_argument(
        "--agent-id",
        type=int,
        required=True,
        help="Agent ID (determines which account to publish to)",
    )
    p.add_argument("--title", "-t", required=True, help="Article title")
    p.add_argument("--digest", help="Article digest/summary")
    p.add_argument("--content", "-c", help="Markdown content (inline string)")
    p.add_argument("--content-file", "-f", help="Path to content file (.md or .html)")
    p.add_argument(
        "--cover", help="Cover image: media:<id>, media library ID (number), or http(s) URL"
    )
    p.set_defaults(func=cmd_create_article)

    # edit-article
    p = sub.add_parser("edit-article", help="Edit an existing article")
    p.add_argument("article_id", type=int, help="Article ID")
    p.add_argument("--title", "-t", help="New title")
    p.add_argument("--digest", help="New digest/summary")
    p.add_argument("--content", "-c", help="New Markdown content (inline string)")
    p.add_argument("--content-file", "-f", help="Path to new content file (.md or .html)")
    p.add_argument(
        "--cover", help="New cover image: media:<id>, media library ID (number), or http(s) URL"
    )
    p.set_defaults(func=cmd_edit_article)

    # sync-article
    p = sub.add_parser("sync-article", help="Sync article edits to WeChat draft")
    p.add_argument("article_id", type=int, help="Article ID")
    p.set_defaults(func=cmd_sync_article)

    # batch-publish
    p = sub.add_parser("batch-publish", help="Batch publish (admin only)")
    p.add_argument("article_ids", type=int, nargs="+", help="Article IDs")
    p.set_defaults(func=cmd_batch_publish)

    # media
    p = sub.add_parser("media", help="List media assets")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--page", type=int, default=1, help="Page number")
    p.set_defaults(func=cmd_media)

    # upload-media
    p = sub.add_parser("upload-media", help="Upload image to media library")
    p.add_argument("file", help="Path to the image file")
    p.add_argument("--tags", help="Comma-separated tags")
    p.add_argument("--description", "-d", help="Description")
    p.set_defaults(func=cmd_upload_media)

    # delete-media
    p = sub.add_parser("delete-media", help="Delete a media asset")
    p.add_argument("media_id", type=int, help="Media asset ID")
    p.set_defaults(func=cmd_delete_media)

    # followers
    p = sub.add_parser("followers", help="View follower statistics")
    p.add_argument("account_id", type=int, help="Account ID")
    p.add_argument("--begin-date", help="Start date (YYYY-MM-DD, default: 7 days ago)")
    p.add_argument("--end-date", help="End date (YYYY-MM-DD, default: yesterday)")
    p.set_defaults(func=cmd_followers)

    # article-stats
    p = sub.add_parser("article-stats", help="View article statistics")
    p.add_argument("account_id", type=int, help="Account ID")
    p.add_argument("--begin-date", help="Start date (YYYY-MM-DD, default: 7 days ago)")
    p.add_argument("--end-date", help="End date (YYYY-MM-DD, default: yesterday)")
    p.set_defaults(func=cmd_article_stats)

    # list-admins
    p = sub.add_parser("list-admins", help="List all admin emails (admin only)")
    p.set_defaults(func=cmd_list_admins)

    # add-admin
    p = sub.add_parser("add-admin", help="Add a runtime admin (admin only)")
    p.add_argument("admin_email", help="Email of the new admin")
    p.set_defaults(func=cmd_add_admin)

    # remove-admin
    p = sub.add_parser("remove-admin", help="Remove a runtime admin (admin only)")
    p.add_argument("admin_email", help="Email of the admin to remove")
    p.set_defaults(func=cmd_remove_admin)

    # list-styles
    p = sub.add_parser("list-styles", help="List all style presets")
    p.add_argument("--full", action="store_true", help="Show full prompt content")
    p.set_defaults(func=cmd_list_styles)

    # edit-style
    p = sub.add_parser("edit-style", help="Edit a style preset")
    p.add_argument("style_id", help="Style preset ID")
    p.add_argument("--name", help="New display name")
    p.add_argument("--description", help="New description")
    p.add_argument("--prompt", help="New prompt template (inline string)")
    p.add_argument("--prompt-file", help="Path to file containing new prompt template")
    p.set_defaults(func=cmd_edit_style)

    # create-style
    p = sub.add_parser("create-style", help="Create a custom style preset")
    p.add_argument("style_id", help="Style ID (English identifier)")
    p.add_argument("--name", "-n", required=True, help="Display name")
    p.add_argument("--description", "-d", default="", help="Description")
    p.add_argument("--prompt", help="Prompt template (inline string)")
    p.add_argument("--prompt-file", help="Path to file containing prompt template")
    p.set_defaults(func=cmd_create_style)

    # delete-style
    p = sub.add_parser("delete-style", help="Delete a custom style preset")
    p.add_argument("style_id", help="Style preset ID to delete")
    p.set_defaults(func=cmd_delete_style)

    # generate-variants
    p = sub.add_parser("generate-variants", help="Generate variant articles")
    p.add_argument("article_id", type=int, help="Source article ID")
    p.add_argument("--agents", required=True, help="Comma-separated agent IDs (e.g. 1,2,3)")
    p.add_argument(
        "--styles", required=True, help="Comma-separated style IDs (e.g. tech,uncle,clickbait)"
    )
    p.add_argument("--wait", "-w", action="store_true", help="Wait for completion")
    p.set_defaults(func=cmd_generate_variants)

    # variant-status
    p = sub.add_parser("variant-status", help="Check variant generation task status")
    p.add_argument("batch_task_id", type=int, help="Batch task ID")
    p.set_defaults(func=cmd_variant_status)

    # variants
    p = sub.add_parser("variants", help="List variant articles for a source")
    p.add_argument("article_id", type=int, help="Source article ID")
    p.set_defaults(func=cmd_variants)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
