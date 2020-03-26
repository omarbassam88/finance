import os
from datetime import timedelta

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
# from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
from flask.helpers import url_for

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.secret_key = 'super secret key'
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.permanent_session_lifetime = timedelta(days = 1)



# Configure CS50 Library to use SQLite database 
db = SQL("sqlite:///finance.db")
# Use in each context instead


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    db = SQL("sqlite:///finance.db")
    # Get user transactions
    stocks = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id=? GROUP BY symbol Having total_shares>0",(session["user_id"]))
    print(stocks)
    # Get Current Price
    quotes={}
    for stock in stocks:
        quotes[stock["symbol"]]= lookup(stock["symbol"])["price"]
    # Get user cash
    cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])[0]["cash"]
    # Go to Portfolio
    return render_template("index.html", stocks=stocks, quotes=quotes,cash=cash)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        quote = lookup(symbol)
        # Checking if Quote is available
        if not quote:
            return apology("Quote not Found",403)
        else:
            shares = request.form.get("shares")
            db = SQL("sqlite:///finance.db")
            # Get current user cash
            rows = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])
            cash = rows[0]["cash"]
            print(cash)
            amount = float(shares)*quote["price"]
            if cash < amount:
                return apology("NOT ENOUGH CASH",403)
            else:
                cash -= amount
                # Add to transactions
                db.execute("INSERT INTO transactions (user_id,symbol,price,shares,amount) VALUES(:user_id,:symbol,:price,:shares,:amount)",user_id=session["user_id"],symbol=quote["symbol"],price=quote["price"],shares=shares,amount=amount)
                # update cash in users
                db.execute("UPDATE users SET cash = :cash WHERE id=:user_id",user_id =session["user_id"],cash=cash)
                return redirect(url_for("index"))
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    db = SQL("sqlite:///finance.db")
    # Get user Transactions
    transactions = db.execute("SELECT * from transactions WHERE user_id=?",(session["user_id"]))
    # Get user Cash
    cash = db.execute("SELECT * FROM users WHERE id=?", session["user_id"])[0]["cash"]
    return render_template("history.html",transactions=transactions,cash=cash)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        db = SQL("sqlite:///finance.db")
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # Make sure a Quote is entered
        if not request.form.get("quote"):
            return apology("Please Enter a quote",400)
        # Getting the Quote 
        quote = lookup(request.form.get("quote"))
        # checking quote availability
        if not quote:
            return apology("Quote not Found",403)
        else:
            return render_template("quoted.html",quote=quote)
        print("quote is",quote)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("usernamenew"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("passwordnew"):
            return apology("must provide password", 400)

        # Ensure password and confirmation match
        elif not request.form.get("passwordnew") == request.form.get("confirmation"):
            return apology("passwords do not match", 400)

        db = SQL("sqlite:///finance.db")

        # unique username constraint violated?
        if db.execute("SELECT * FROM users WHERE username=?", request.form.get("usernamenew")):
            return apology("username taken", 400)

        # hash the password and insert a new user in the database
        hash = generate_password_hash(request.form.get("passwordnew"))
        new_user_id = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",username=request.form.get("usernamenew"), hash=hash)

        # Remember which user has logged in
        session["user_id"] = new_user_id

        # Display a flash message
        flash("Registered!")

        # Redirect user to home page
        return redirect(url_for("index"))

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        # Check if user has stock
        db = SQL("sqlite:///finance.db")
        # Get user transactions
        symbol=request.form.get("symbol")
        shares=int(request.form.get("shares"))
        stock = db.execute("SELECT SUM(shares) as total_shares FROM transactions WHERE user_id=? and symbol=? GROUP BY symbol Having total_shares>0",(session["user_id"],symbol))
        print(stock)

        if len(stock) !=1:   
            return apology("You don't own this Quote")
        elif shares > stock[0]["total_shares"]:
            return apology("You don't have enough shares")
        else:
            current_price=lookup(symbol)["price"]
            amount= float(shares*current_price)
            # insert Transaction into Database
            shares*=(-1)
            db.execute("INSERT INTO transactions (user_id,symbol,price,shares,amount) VALUES(:user_id,:symbol,:price,:shares,:amount)",user_id=session["user_id"],symbol=symbol,price=current_price,shares=shares,amount=amount)
            # update user cash
            cash=db.execute("SELECT * FROM users WHERE id=?", session["user_id"])[0]["cash"]
            cash+=amount
            db.execute("UPDATE users SET cash = :cash WHERE id=:user_id",user_id =session["user_id"],cash=cash)
            # Back to Portfolio
            return redirect(url_for("index"))
    else:
        return render_template("sell.html")


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
