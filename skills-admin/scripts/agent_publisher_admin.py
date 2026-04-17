#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx>=0.27.0",
# ]
# ///
"""
Agent Publisher Admin CLI — 管理后台

Agent 管理、AI 生成、风格预设、多风格改写、权限管理。

Usage:
    uv run agent_publisher_admin.py <command> [options]

Commands:
    auth               管理员认证
    whoami             查看身份
    agents             列出 Agent
    create-agent       创建 Agent
    update-agent       更新 Agent
    generate           AI 生成文章
    collect            采集素材
    task               查看任务状态
    list-styles        查看风格预设
    create-style       创建风格
    edit-style         编辑风格
    delete-style       删除风格
    generate-variants  多风格改写
    variants           查看改写版本
    list-admins        管理员列表
    add-admin          添加管理员
    remove-admin       移除管理员
    accounts-all       查看所有公众号

Environment:
    AP_URL     后端地址 (default: http://localhost:9099)
    AP_EMAIL   管理员邮箱
    AP_TOKEN   Skill token
"""

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_URL = "http://localhost:9099"
TOKEN_FILE = os.path.expanduser("~/.agent-publisher-token")


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


def cmd_whoami(args):
    base = get_base_url(args)
    token = require_token(args)
    pp(api("GET", f"{base}/api/skills/whoami", token=token))


# ── Agent ──

def cmd_agents(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/agents", token=token)
    if not result:
        print("No agents.")
        return
    for ag in result:
        active = "ON" if ag.get("is_active") else "OFF"
        style = ag.get("default_style_id") or "-"
        print(f"  [{ag['id']}] {ag['name']}  topic={ag['topic']}  style={style}  cron={ag.get('schedule_cron', '-')}  {active}")


def cmd_create_agent(args):
    base = get_base_url(args)
    token = require_token(args)
    payload = {"name": args.name, "topic": args.topic, "account_id": args.account_id,
               "schedule_cron": args.cron}
    if args.description:
        payload["description"] = args.description
    if args.default_style:
        payload["default_style_id"] = args.default_style
    result = api("POST", f"{base}/api/skills/agents", token=token, json=payload)
    print(f"Agent created: id={result['id']} name={result['name']}")


def cmd_update_agent(args):
    base = get_base_url(args)
    token = require_token(args)
    payload = {}
    if args.name:
        payload["name"] = args.name
    if args.topic:
        payload["topic"] = args.topic
    if args.description:
        payload["description"] = args.description
    if args.default_style is not None:
        payload["default_style_id"] = args.default_style if args.default_style else None
    if args.cron:
        payload["schedule_cron"] = args.cron
    if args.active is not None:
        payload["is_active"] = args.active
    if not payload:
        print("Error: No fields to update.", file=sys.stderr)
        sys.exit(1)
    result = api("PUT", f"{base}/api/skills/agents/{args.agent_id}", token=token, json=payload)
    print(f"Agent {result['id']} updated: name={result.get('name')} style={result.get('default_style_id', '-')}")


# ── Generate & Collect ──

def cmd_generate(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/agents/{args.agent_id}/generate", token=token)
    task_id = result.get("task_id")
    print(f"Generation started: task_id={task_id}")
    if args.wait:
        _poll_task(base, token, task_id)


def cmd_collect(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/agents/{args.agent_id}/collect", token=token)
    print(f"Collected {result.get('total_collected', 0)} materials for agent {args.agent_id}")
    for src, count in (result.get("collect_summary") or {}).items():
        print(f"  {src}: {count}")


def cmd_task(args):
    base = get_base_url(args)
    token = require_token(args)
    pp(api("GET", f"{base}/api/skills/tasks/{args.task_id}", token=token))


def _poll_task(base, token, task_id):
    print("Waiting...")
    for _ in range(60):
        time.sleep(5)
        task = api("GET", f"{base}/api/skills/tasks/{task_id}", token=token)
        status = task.get("status", "")
        if status in ("success", "failed"):
            print(f"\n{'Done!' if status == 'success' else 'Failed!'}")
            if task.get("result"):
                pp(task["result"])
            return
    print("Timeout.")


# ── Style ──

def cmd_list_styles(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/style-presets", token=token)
    if not result:
        print("No styles.")
        return
    for s in result:
        tag = "builtin" if s.get("is_builtin") else "custom"
        prompt = s.get("prompt", "")
        preview = (prompt[:80] + "...") if len(prompt) > 80 else prompt
        print(f"  [{s['style_id']}] {s['name']} ({tag})")
        if args.full:
            print(f"    {prompt}")
        else:
            print(f"    {preview}")


def cmd_create_style(args):
    base = get_base_url(args)
    token = require_token(args)
    prompt = args.prompt or ""
    if args.prompt_file:
        if not os.path.isfile(args.prompt_file):
            print(f"Error: File not found: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read()
    result = api("POST", f"{base}/api/skills/style-presets", token=token, json={
        "style_id": args.style_id, "name": args.name,
        "description": args.description or "", "prompt": prompt,
    })
    print(f"Style created: {result.get('style_id')}")


def cmd_edit_style(args):
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
        if not os.path.isfile(args.prompt_file):
            print(f"Error: File not found: {args.prompt_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            payload["prompt"] = f.read()
    if not payload:
        print("Error: No fields.", file=sys.stderr)
        sys.exit(1)
    result = api("PUT", f"{base}/api/skills/style-presets/{args.style_id}", token=token, json=payload)
    print(f"Style '{result.get('style_id')}' updated")


def cmd_delete_style(args):
    base = get_base_url(args)
    token = require_token(args)
    api("DELETE", f"{base}/api/skills/style-presets/{args.style_id}", token=token)
    print(f"Style {args.style_id} deleted")


# ── Variants ──

def cmd_generate_variants(args):
    base = get_base_url(args)
    token = require_token(args)
    agent_ids = [int(x.strip()) for x in args.agents.split(",")]
    style_ids = [x.strip() for x in args.styles.split(",")]
    result = api("POST", f"{base}/api/skills/articles/{args.article_id}/variants",
                 token=token, json={"agent_ids": agent_ids, "style_ids": style_ids})
    if result.get("ok"):
        print(f"Variant generation started: batch_task_id={result.get('batch_task_id')} total={result.get('total')}")
        if args.wait and result.get("batch_task_id"):
            _poll_task(base, token, result["batch_task_id"])
    else:
        print(f"Failed: {result}")


def cmd_variants(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/articles/{args.article_id}/variants", token=token)
    if not result:
        print("No variants.")
        return
    for v in result:
        print(f"  [{v['id']}] {v.get('title', '-')}  style={v.get('variant_style', '-')}  agent={v.get('agent_name', v.get('agent_id'))}")


# ── Admin ──

def cmd_list_admins(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/admins", token=token)
    for src, emails in [("env", result.get("env_admins", [])), ("runtime", result.get("runtime_admins", []))]:
        for e in emails:
            print(f"  [{src}] {e}")


def cmd_add_admin(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("POST", f"{base}/api/skills/admins", token=token, json={"email": args.admin_email})
    print(result.get("message", "Done"))


def cmd_remove_admin(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("DELETE", f"{base}/api/skills/admins", token=token, json={"email": args.admin_email})
    print(result.get("message", "Done"))


def cmd_accounts_all(args):
    base = get_base_url(args)
    token = require_token(args)
    result = api("GET", f"{base}/api/skills/accounts/all", token=token)
    if not result:
        print("No accounts.")
        return
    for acc in result:
        print(f"  [{acc['id']}] {acc['name']}  appid={acc['appid']}  owner={acc.get('owner_email', '-')}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="agent_publisher_admin", description="Agent Publisher Admin CLI")
    parser.add_argument("--url", help="Backend URL (env: AP_URL)")
    parser.add_argument("--token", help="Skill token (env: AP_TOKEN)")
    parser.add_argument("--email", help="Email (env: AP_EMAIL)")
    sub = parser.add_subparsers(dest="command", required=True)

    # auth
    p = sub.add_parser("auth", help="管理员认证")
    p.add_argument("--email", "-e", dest="email")
    p.set_defaults(func=cmd_auth)

    sub.add_parser("whoami", help="查看身份").set_defaults(func=cmd_whoami)

    # agents
    sub.add_parser("agents", help="列出 Agent").set_defaults(func=cmd_agents)

    p = sub.add_parser("create-agent", help="创建 Agent")
    p.add_argument("--name", "-n", required=True)
    p.add_argument("--topic", "-t", required=True)
    p.add_argument("--account-id", type=int, required=True)
    p.add_argument("--cron", default="0 8 * * *")
    p.add_argument("--description")
    p.add_argument("--default-style")
    p.set_defaults(func=cmd_create_agent)

    p = sub.add_parser("update-agent", help="更新 Agent")
    p.add_argument("agent_id", type=int)
    p.add_argument("--name")
    p.add_argument("--topic")
    p.add_argument("--description")
    p.add_argument("--default-style")
    p.add_argument("--cron")
    p.add_argument("--active", type=lambda x: x.lower() in ("true", "1", "yes"))
    p.set_defaults(func=cmd_update_agent)

    # generate / collect / task
    p = sub.add_parser("generate", help="AI 生成文章")
    p.add_argument("agent_id", type=int)
    p.add_argument("--wait", "-w", action="store_true")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("collect", help="采集素材")
    p.add_argument("agent_id", type=int)
    p.set_defaults(func=cmd_collect)

    p = sub.add_parser("task", help="查看任务状态")
    p.add_argument("task_id", type=int)
    p.set_defaults(func=cmd_task)

    # styles
    p = sub.add_parser("list-styles", help="查看风格预设")
    p.add_argument("--full", action="store_true")
    p.set_defaults(func=cmd_list_styles)

    p = sub.add_parser("create-style", help="创建风格")
    p.add_argument("style_id")
    p.add_argument("--name", "-n", required=True)
    p.add_argument("--description", "-d", default="")
    p.add_argument("--prompt")
    p.add_argument("--prompt-file")
    p.set_defaults(func=cmd_create_style)

    p = sub.add_parser("edit-style", help="编辑风格")
    p.add_argument("style_id")
    p.add_argument("--name")
    p.add_argument("--description")
    p.add_argument("--prompt")
    p.add_argument("--prompt-file")
    p.set_defaults(func=cmd_edit_style)

    p = sub.add_parser("delete-style", help="删除风格")
    p.add_argument("style_id")
    p.set_defaults(func=cmd_delete_style)

    # variants
    p = sub.add_parser("generate-variants", help="多风格改写")
    p.add_argument("article_id", type=int)
    p.add_argument("--agents", required=True, help="Comma-separated agent IDs")
    p.add_argument("--styles", required=True, help="Comma-separated style IDs")
    p.add_argument("--wait", "-w", action="store_true")
    p.set_defaults(func=cmd_generate_variants)

    p = sub.add_parser("variants", help="查看改写版本")
    p.add_argument("article_id", type=int)
    p.set_defaults(func=cmd_variants)

    # admin
    sub.add_parser("list-admins", help="管理员列表").set_defaults(func=cmd_list_admins)

    p = sub.add_parser("add-admin", help="添加管理员")
    p.add_argument("admin_email")
    p.set_defaults(func=cmd_add_admin)

    p = sub.add_parser("remove-admin", help="移除管理员")
    p.add_argument("admin_email")
    p.set_defaults(func=cmd_remove_admin)

    sub.add_parser("accounts-all", help="查看所有公众号").set_defaults(func=cmd_accounts_all)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
