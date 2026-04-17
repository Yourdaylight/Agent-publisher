#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Agent Publisher CLI — 微信公众号发布工具

本地编辑好内容，通过 CLI 上传、美化排版、发布到微信草稿箱。

Usage:
    uv run agent_publisher.py <command> [options]

Commands:
    auth            邮箱认证，获取 token
    whoami          查看当前身份
    accounts        列出我的公众号
    create-account  绑定公众号
    articles        列出文章
    article         查看文章详情
    create-article  上传文章（Markdown/HTML）
    edit-article    编辑文章
    beautify        wenyan 主题排版
    ai-beautify     AI 智能美化
    publish         发布到微信草稿箱
    sync-article    同步编辑到草稿箱
    batch-publish   批量发布（管理员）
    media           列出素材
    upload-media    上传图片到素材库
    delete-media    删除素材
    followers       粉丝趋势
    article-stats   文章阅读数据

Environment:
    AP_URL          后端地址 (default: http://localhost:9099)
    AP_TOKEN        Skill token
    AP_EMAIL        认证邮箱
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
    return (getattr(args, "url", None) or os.environ.get("AP_URL") or DEFAULT_URL).rstrip("/")


def save_token(token, email):
    with open(TOKEN_FILE, "w") as f:
        json.dump({"token": token, "email": email, "ts": int(time.time())}, f)
    os.chmod(TOKEN_FILE, 0o600)


def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            return json.load(f)
    return None


def resolve_token(args):
    token = getattr(args, "token", None) or os.environ.get("AP_TOKEN")
    if token:
        return token
    saved = load_token()
    if saved:
        return saved.get("token")
    return None


def api(method, url, token=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
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
    token = resolve_token(args)
    if token:
        return token
    email = getattr(args, "email", None) or os.environ.get("AP_EMAIL")
    if email:
        base = get_base_url(args)
        result = api("POST", f"{base}/api/skills/auth", json={"email": email})
        save_token(result["token"], result["email"])
        return result["token"]
    print('Error: No token. Run "auth" first or set AP_EMAIL.', file=sys.stderr)
    sys.exit(1)


def pp(data):
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_auth(args):
    base = get_base_url(args)
    email = args.email or os.environ.get("AP_EMAIL")
    if not email:
        print("Error: --email is required.", file=sys.stderr)
        sys.exit(1)
    result = api("POST", f"{base}/api/skills/auth", json={"email": email})
    save_token(result["token"], result["email"])
    print(f"Authenticated as {result['email']} (admin={result['is_admin']})")
    print(f"Token saved to {TOKEN_FILE}")


def cmd_whoami(args):
    base = get_base_url(args)
    token = require_token(args)
    pp(api("GET", f"{base}/api/skills/whoami", token=token))


def cmd_accounts(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/accounts", token=token)
    if not result:
        print("No accounts. Use create-account to add one.")
        return
    for acc in result:
        print(f"  [{acc['id']}] {acc['name']}  appid={acc['appid']}")


def cmd_create_account(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/accounts", token=token, json={
        "name": args.name, "appid": args.appid, "appsecret": args.appsecret,
    })
    print(f"Account created: id={result['id']} name={result['name']}")


def cmd_articles(args):
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
        print(f"  [{art['id']}] {art.get('title', 'Untitled')}  status={art.get('status')}")


def cmd_article(args):
    base = get_base_url(args)
    token = require_token(args)
    pp(api("GET", f"{base}/api/skills/articles/{args.article_id}", token=token))


def cmd_create_article(args):
    base = get_base_url(args)
    token = require_token(args)

    content = ""
    html_content = ""
    if args.content_file:
        if not os.path.isfile(args.content_file):
            print(f"Error: File not found: {args.content_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.content_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        if args.content_file.endswith((".html", ".htm")):
            html_content = file_content
        else:
            content = file_content
    elif args.content:
        content = args.content

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
    print(f"Article created: id={result['id']} title={result['title']}")


def cmd_edit_article(args):
    base = get_base_url(args)
    token = require_token(args)
    payload = {}
    if args.title:
        payload["title"] = args.title
    if args.digest:
        payload["digest"] = args.digest
    if args.content_file:
        if not os.path.isfile(args.content_file):
            print(f"Error: File not found: {args.content_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.content_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        if args.content_file.endswith((".html", ".htm")):
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
        print("Error: No fields to update.", file=sys.stderr)
        sys.exit(1)
    result = api("PUT", f"{base}/api/skills/articles/{args.article_id}", token=token, json=payload)
    print(f"Article {result['id']} updated: title={result['title']}")


def cmd_beautify(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/beautify", token=token,
                 json={"theme": args.theme or "default"})
    if result.get("ok"):
        print(f"Article {args.article_id} beautified with theme '{result.get('theme', 'default')}'")
    else:
        print(f"Failed: {result}")


def cmd_ai_beautify(args):
    base = get_base_url(args)
    token = require_token(args)
    payload = {}
    if args.style_hint:
        payload["style_hint"] = args.style_hint
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/ai-beautify",
                 token=token, json=payload)
    if result.get("ok"):
        print(f"Article {args.article_id} AI-beautified")
    else:
        print(f"Failed: {result}")


def cmd_publish(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/publish", token=token)
    if result.get("ok"):
        print(f"Published! media_id={result.get('media_id')}")
    else:
        print(f"Failed: {result}")


def cmd_sync_article(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/sync", token=token)
    if result.get("ok"):
        print(f"Article {args.article_id} synced to WeChat draft box.")
    else:
        print(f"Sync failed: {result}")


def cmd_batch_publish(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/articles/batch-publish", token=token,
                 json={"article_ids": args.article_ids})
    for r in result:
        status = "OK" if r.get("success") else "FAIL"
        msg = r.get("media_id") or r.get("error", "")
        print(f"  [{status}] article {r['article_id']}: {msg}")


def cmd_media(args):
    base = get_base_url(args)
    token = require_token(args)
    params = []
    if args.tag:
        params.append(f"tag={args.tag}")
    url = f"{base}/api/skills/media"
    if params:
        url += "?" + "&".join(params)
    result = api("GET", url, token=token)
    if not result:
        print("No media assets.")
        return
    for m in result:
        print(f"  [{m['id']}] {m['filename']}  {m.get('file_size', 0) / 1024:.1f}KB  url={m.get('url')}")


def cmd_upload_media(args):
    base = get_base_url(args)
    token = require_token(args)
    if not os.path.isfile(args.file):
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    filename = os.path.basename(args.file)
    with open(args.file, "rb") as f:
        file_content = f.read()
    headers = {"Authorization": f"Bearer {token}"}
    data = {}
    if args.tags:
        data["tags"] = args.tags
    if args.description:
        data["description"] = args.description
    try:
        resp = httpx.post(f"{base}/api/skills/media", headers=headers,
                          files={"file": (filename, file_content)}, data=data, timeout=120)
    except httpx.ConnectError:
        print(f"Error: Cannot connect to {base}", file=sys.stderr)
        sys.exit(1)
    if resp.status_code >= 400:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    result = resp.json()
    print(f"Uploaded: id={result['id']} filename={result['filename']} url={base}{result.get('url', '')}")


def cmd_delete_media(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("DELETE", f"{base}/api/skills/media/{args.media_id}", token=token)
    print(f"Deleted media {args.media_id}" if result.get("ok") else f"Failed: {result}")


def cmd_followers(args):
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
    pp(api("GET", url, token=token))


def cmd_article_stats(args):
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
    pp(api("GET", url, token=token))


# ---------------------------------------------------------------------------
# CLI parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="agent_publisher",
        description="Agent Publisher CLI — 微信公众号发布工具",
    )
    parser.add_argument("--url", help="Backend URL (env: AP_URL)")
    parser.add_argument("--token", help="Skill token (env: AP_TOKEN)")
    parser.add_argument("--email", help="Email for auto-auth (env: AP_EMAIL)")

    sub = parser.add_subparsers(dest="command", required=True)

    # auth
    p = sub.add_parser("auth", help="邮箱认证")
    p.add_argument("--email", "-e", dest="email", help="Whitelisted email")
    p.set_defaults(func=cmd_auth)

    # whoami
    sub.add_parser("whoami", help="查看身份").set_defaults(func=cmd_whoami)

    # accounts
    sub.add_parser("accounts", help="列出公众号").set_defaults(func=cmd_accounts)

    # create-account
    p = sub.add_parser("create-account", help="绑定公众号")
    p.add_argument("--name", "-n", required=True)
    p.add_argument("--appid", required=True)
    p.add_argument("--appsecret", required=True)
    p.set_defaults(func=cmd_create_account)

    # articles
    p = sub.add_parser("articles", help="列出文章")
    p.add_argument("--status", help="Filter: draft/published")
    p.set_defaults(func=cmd_articles)

    # article
    p = sub.add_parser("article", help="查看文章详情")
    p.add_argument("article_id", type=int)
    p.set_defaults(func=cmd_article)

    # create-article
    p = sub.add_parser("create-article", help="上传文章")
    p.add_argument("--agent-id", type=int, required=True, help="Agent ID")
    p.add_argument("--title", "-t", required=True)
    p.add_argument("--digest", help="摘要")
    p.add_argument("--content", "-c", help="Markdown content (inline)")
    p.add_argument("--content-file", "-f", help="Path to .md or .html file")
    p.add_argument("--cover", help="Cover: media:<id> or URL")
    p.set_defaults(func=cmd_create_article)

    # edit-article
    p = sub.add_parser("edit-article", help="编辑文章")
    p.add_argument("article_id", type=int)
    p.add_argument("--title", "-t")
    p.add_argument("--digest")
    p.add_argument("--content", "-c")
    p.add_argument("--content-file", "-f")
    p.add_argument("--cover")
    p.set_defaults(func=cmd_edit_article)

    # beautify
    p = sub.add_parser("beautify", help="wenyan 主题排版")
    p.add_argument("article_id", type=int)
    p.add_argument("--theme", default="default",
                   help="default/orangeheart/rainbow/lapis/pie/maize/purple/phycat")
    p.set_defaults(func=cmd_beautify)

    # ai-beautify
    p = sub.add_parser("ai-beautify", help="AI 智能美化")
    p.add_argument("article_id", type=int)
    p.add_argument("--style-hint", default="", help="Style direction for AI")
    p.set_defaults(func=cmd_ai_beautify)

    # publish
    p = sub.add_parser("publish", help="发布到微信草稿箱")
    p.add_argument("article_id", type=int)
    p.set_defaults(func=cmd_publish)

    # sync-article
    p = sub.add_parser("sync-article", help="同步编辑到草稿箱")
    p.add_argument("article_id", type=int)
    p.set_defaults(func=cmd_sync_article)

    # batch-publish
    p = sub.add_parser("batch-publish", help="批量发布（管理员）")
    p.add_argument("article_ids", type=int, nargs="+")
    p.set_defaults(func=cmd_batch_publish)

    # media
    p = sub.add_parser("media", help="列出素材")
    p.add_argument("--tag")
    p.set_defaults(func=cmd_media)

    # upload-media
    p = sub.add_parser("upload-media", help="上传图片")
    p.add_argument("file", help="File path")
    p.add_argument("--tags")
    p.add_argument("--description", "-d")
    p.set_defaults(func=cmd_upload_media)

    # delete-media
    p = sub.add_parser("delete-media", help="删除素材")
    p.add_argument("media_id", type=int)
    p.set_defaults(func=cmd_delete_media)

    # followers
    p = sub.add_parser("followers", help="粉丝趋势")
    p.add_argument("account_id", type=int)
    p.add_argument("--begin-date")
    p.add_argument("--end-date")
    p.set_defaults(func=cmd_followers)

    # article-stats
    p = sub.add_parser("article-stats", help="文章阅读数据")
    p.add_argument("account_id", type=int)
    p.add_argument("--begin-date")
    p.add_argument("--end-date")
    p.set_defaults(func=cmd_article_stats)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
