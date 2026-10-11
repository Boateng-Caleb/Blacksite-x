"""Layer 5 - HTTP routes: HTML pages (presentation layer entry points)."""
from flask import Blueprint, redirect, render_template, url_for

from ..security import current_user, page_login_required
from ..services.item_service import CATEGORIES

bp = Blueprint("pages", __name__)


@bp.get("/")
def explore():
    return render_template("explore.html", page="explore", categories=CATEGORIES)


@bp.get("/login")
def login():
    return redirect(url_for("pages.explore")) if current_user() else render_template("login.html", page="login")


@bp.get("/signup")
def signup():
    return redirect(url_for("pages.explore")) if current_user() else render_template("signup.html", page="signup")


@bp.get("/sell")
@page_login_required
def sell(user):
    return render_template("sell.html", page="sell", categories=CATEGORIES)


@bp.get("/items/<item_id>")
def item(item_id):
    return render_template("item.html", page="item", item_id=item_id)


@bp.get("/orders")
@page_login_required
def orders(user):
    return render_template("orders.html", page="orders")
