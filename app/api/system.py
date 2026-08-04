from sanic import Blueprint, Request
from sanic.response import html, json

system_bp = Blueprint("system")


@system_bp.get("/health")
async def health(_: Request):
    return json({"status": "ok"})


@system_bp.get("/docs")
async def docs(_: Request):
    return html(
        """
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <title>Account Balance API Service - Sanic Docs</title>
          </head>
          <body>
            <h1>Account Balance API Service</h1>
            <h2>Sanic REST API</h2>
            <ul>
              <li>POST /api/v1/auth/login</li>
              <li>GET /api/v1/me</li>
              <li>GET /api/v1/me/accounts</li>
              <li>GET /api/v1/me/payments</li>
              <li>POST /api/v1/admin/users</li>
              <li>GET /api/v1/admin/users</li>
              <li>PATCH /api/v1/admin/users/&lt;user_id&gt;</li>
              <li>DELETE /api/v1/admin/users/&lt;user_id&gt;</li>
              <li>POST /api/v1/payments/webhook</li>
            </ul>
          </body>
        </html>
        """
    )
