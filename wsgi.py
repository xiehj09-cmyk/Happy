"""WSGI 入口 · 供 Waitress / gunicorn 使用"""

from app import app, init_db

with app.app_context():
    init_db()
