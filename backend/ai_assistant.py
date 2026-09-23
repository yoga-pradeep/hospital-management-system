"""
ai_assistant.py
----------------
Exposes POST /api/assistant/chat.

Flow for every request:
  1. Flask verifies the JWT as usual (@jwt_required) -> we get the real,
     already-authenticated role/user_id/username. Nothing here bypasses
     the existing JWT/RBAC system; it reuses it.
  2. We spawn/connect to mcp_server.py as an MCP client (stdio transport)
     and ask it what tools exist (list_tools).
  3. We hand those tools + the user's message to a local open-source LLM
     running in Ollama (e.g. "llama3.2"), which decides whether it needs
     to call a tool to answer.
  4. If the model asks for a tool call, we IGNORE any role/user_id the
     model supplied and inject the authenticated caller's real role/user_id
     before actually invoking the MCP tool. This is what keeps RBAC safe:
     the model can influence *which* tool and *what filters* (e.g. date,
     department) but never *whose data* gets returned.
  5. The tool result is fed back to the model, which writes the final
     natural-language reply.

Requires a local Ollama instance (https://ollama.com) with a tool-calling
capable open model pulled, e.g.:
    ollama pull llama3.2
Configure the model/host via OLLAMA_MODEL / OLLAMA_HOST env vars
(see config.py). No external/paid API key is used anywhere.
"""

import asyncio
import json
import os
import sys

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import ollama

assistant_bp = Blueprint("assistant", __name__, url_prefix="/api/assistant")

OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

MCP_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mcp_server.py")

MAX_TOOL_ROUNDS = 4  # safety cap on how many tool-call loops we allow per message


def _mcp_tool_to_ollama_tool(mcp_tool) -> dict:
    """Convert an MCP tool description into the JSON schema Ollama expects."""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema or {"type": "object", "properties": {}},
        },
    }


async def _run_assistant(user_message: str, role: str, user_id: str, username: str) -> str:
    client = ollama.AsyncClient(host=OLLAMA_HOST)

    server_params = StdioServerParameters(command=sys.executable, args=[MCP_SERVER_SCRIPT])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            ollama_tools = [_mcp_tool_to_ollama_tool(t) for t in tools_result.tools]

            system_prompt = (
                "You are the AI assistant embedded in a Hospital Management System. "
                f"The person you are talking to is '{username}', logged in with role "
                f"'{role}'. Use the available tools to look up REAL, live data before "
                "answering any question about appointments, doctors, schedules, or "
                "hospital stats -- never invent appointment details. If a tool returns "
                "an 'error' field, explain the limitation to the user politely instead "
                "of guessing. Keep answers short and clear. When calling a tool, you do "
                "not need to worry about identity fields like role/user_id -- the system "
                "fills those in for you automatically and will ignore any values you set."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            for _ in range(MAX_TOOL_ROUNDS):
                response = await client.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    tools=ollama_tools,
                )
                msg = response["message"]
                messages.append(msg)

                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    return msg.get("content", "").strip() or "I couldn't come up with a reply."

                for call in tool_calls:
                    fn_name = call["function"]["name"]
                    fn_args = call["function"].get("arguments") or {}

                    # SECURITY: always override identity fields with the
                    # authenticated caller's real values, regardless of what
                    # the model supplied.
                    fn_args["role"] = role
                    fn_args["user_id"] = str(user_id)

                    try:
                        tool_result = await session.call_tool(fn_name, fn_args)
                        result_text = "".join(
                            part.text for part in tool_result.content if hasattr(part, "text")
                        )
                    except Exception as exc:  # noqa: BLE001
                        result_text = json.dumps({"error": f"Tool call failed: {exc}"})

                    messages.append({
                        "role": "tool",
                        "content": result_text,
                    })

            return "I looked into that but couldn't finish in time. Please try rephrasing."


@assistant_bp.route("/chat", methods=["POST"])
@jwt_required()
def chat():
    data = request.get_json() or {}
    user_message = (data.get("message") or "").strip()

    if not user_message:
        return jsonify({"message": "message is required"}), 400

    claims = get_jwt()
    role = claims.get("role")
    username = claims.get("username")
    user_id = get_jwt_identity()

    try:
        reply = asyncio.run(_run_assistant(user_message, role, user_id, username))
    except Exception as exc:  # noqa: BLE001
        return jsonify({
            "message": "AI assistant is unavailable. Is Ollama running locally?",
            "error": str(exc),
        }), 503

    return jsonify({"reply": reply}), 200


@assistant_bp.route("/health", methods=["GET"])
@jwt_required()
def health():
    """Quick check that Ollama is reachable, without going through MCP/tools."""
    try:
        ollama.Client(host=OLLAMA_HOST).list()
        return jsonify({"status": "ok", "model": OLLAMA_MODEL}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "unavailable", "error": str(exc)}), 503
