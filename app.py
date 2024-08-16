import datetime

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Show portfolio of stocks"""
    if request.method == "POST":
        if request.form['button'] == 'add-money':
            db.execute("UPDATE users SET cash = cash + :money WHERE id = :id", money=request.form.get('money'), id=session["user_id"])
        return redirect("/")
    else:
        username = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0]["username"]
        grand_total = cash_avail = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
        info = db.execute("SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol", session["user_id"])
        print(info)
        for transaction in info:
            if transaction['total_shares'] > 0:        
                transaction['price'] = usd(float(lookup(transaction['symbol'])['price']))
                transaction['total_value'] = usd(int(transaction['total_shares']) * float(lookup(transaction['symbol'])['price']))
                grand_total += float(transaction['total_value'].lstrip('$').replace(',', ''))
            else:
                info.remove(transaction)
            
        return render_template("index.html", username=username, time=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), cash_avail=usd(cash_avail), info=info, grand_total=usd(grand_total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    cash_avail = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    if request.method == "POST":
        if lookup(request.form.get('symbol')):
            latest_symbol = request.form.get('symbol')
        else:
            return apology("invalid symbol", 403)
        
        if not request.form.get('shares').isdigit():
            return apology("must provide non-negative shares", 403)
        else:
            latest_no_shares = int(request.form.get('shares'))

        if request.form['button'] == 'check-prices':
            info = lookup(latest_symbol)
            info['total_cost'] = usd(int(request.form.get('shares')) * float(info['price']))
            info['max_shares'] = int(cash_avail // int(float(info['price'])))

            return render_template(
                        "buy.html", 
                        cash_avail=usd(cash_avail),
                        symbol=latest_symbol,
                        shares=latest_no_shares,
                        info=info
            )
        elif request.form['button'] == 'buy':
            # Add the date and time to the transactions table
            db.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, symbol TEXT, shares INTEGER, price REAL, cash_avail REAL,datetime TEXT)")
            if not request.form.get('shares') == '0':
                value = int(request.form.get('shares')) * float(lookup(latest_symbol)['price'])
                if cash_avail > value:
                    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_avail - value, session["user_id"])
                    db.execute("INSERT INTO transactions (user_id, action, symbol, shares, price, cash_avail, datetime) VALUES (?, ?, ?, ?, ?, ?, ?)", session["user_id"], "Buy", latest_symbol, request.form.get('shares'), lookup(latest_symbol)['price'], cash_avail - value, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                    flash(f"Bought {request.form.get('shares')} shares of {latest_symbol} for {usd(value)} at {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    return apology("not enough cash", 403)
            else:
                return apology("cannot buy 0 shares", 403)

            return redirect("/")
    else:
        return render_template(
            "buy.html", 
            cash_avail=usd(cash_avail),
            shares=None
        )


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY datetime DESC", user_id)

    for transaction in transactions:
        transaction['total_value'] = usd(abs(int(transaction['shares'])) * float(transaction['price']))
        transaction['price'] = usd(float(transaction['price']))
        transaction['cash_avail'] = usd(float(transaction['cash_avail']))

        # Display positive shares for sell actions
        if transaction['action'] == 'Sell':
            transaction['shares'] = abs(transaction['shares'])

    return render_template("history.html", transactions=transactions)


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
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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
        symbols = request.form.get("symbol").split(",")
        stocks = []
        for s in symbols:
            stocks.append(lookup(s))
        
        if stocks[0]:
            return render_template("quoted.html", stocks=stocks)
        else:
            return apology("invalid symbols", 403)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
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
        try: 
            rows = db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), generate_password_hash(request.form.get("password")))
        except ValueError:
            return apology("username already exists", 403)
        
        # Redirect user to home page
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")
    
    


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    cash_avail = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    if request.method == "POST":
        if not request.form.get('shares').isdigit():
            return apology("must provide non-negative shares", 403)
        
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # Check if the user owns the stock
        user_id = session["user_id"]
        user_shares = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)
        if not user_shares or sum(row["shares"] for row in user_shares) < shares:
            return apology("you do not own that many shares", 403)

        # Sell the shares
        stock_price = lookup(symbol)["price"]
        db.execute("INSERT INTO transactions (user_id, action, symbol, shares, price, cash_avail, datetime) VALUES (?, ?, ?, ?, ?, ?, ?)", user_id, "Sell", symbol, -shares, stock_price, cash_avail + stock_price * shares, datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

        # Update the user's cash
        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_avail + stock_price * shares, user_id)

        flash(f"Sold {shares} shares of {symbol} for {usd(stock_price * shares)} at {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
        return redirect("/")

    else:
        # Get the user's stocks
        user_id = session["user_id"]
        user_stocks = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", stocks=user_stocks)