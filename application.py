import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

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
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    #trying to come up with some code to find out how many rows we need which will correlate with the number of symbols pertainig to our user in table stocks
    rows = db.execute("SELECT * FROM stocks WHERE user_id = :user_id", user_id=session["user_id"])
    c = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
    cash = usd(c[0]["cash"])

    
    sum_total = c[0]["cash"]
    for row in rows:
        stock = lookup(row["symbol"])
        row["price"] = usd(stock['price'])
        last_login_price = db.execute("SELECT price FROM prices WHERE user_id = :user_id and symbol = :symbol", user_id=session["user_id"], symbol=row["symbol"])
        
        if not last_login_price:
            row["color"] = 0
        else:
            row["color"] = stock['price'] - last_login_price[0]["price"]
        
        row["total"] = usd(row["amount"] * stock['price'])
        sum_total += (row["amount"] * stock['price'])

    sum_total = usd(sum_total)

    return render_template("index.html", cash=cash, rows=rows, sum_total=sum_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""


    if request.method == "POST":
        user_id = session["user_id"]
        stock = lookup(request.form.get("symbol"))
        if stock == None:
            return apology("Must input valid stock symbol")

        price =  stock['price']
        symbol = stock['symbol']
        name = stock['name']
        quantity = request.form.get("shares")
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id=user_id)

        cost_of_buy = price * int(quantity)
        new_cash = cash[0]["cash"] - cost_of_buy

        if cost_of_buy > cash[0]["cash"]:
            return apology("Insufficient Funds")

        elif not db.execute("SELECT * FROM stocks WHERE user_id = :user_id and symbol = :symbol", user_id=session["user_id"], symbol=stock['symbol']):
            db.execute("INSERT INTO stocks (user_id, symbol, amount, company) VALUES (:user_id, :symbol, :amount, :company)", user_id=session["user_id"], symbol=stock['symbol'], amount=quantity, company=name)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=new_cash, id=session["user_id"])
            trans_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute("INSERT INTO transactions (user_id, symbol, amount, datetime, cost) VALUES (:user_id, :symbol, :amount, :datetime, :cost)", user_id=session["user_id"], symbol=stock['symbol'], amount=quantity, datetime=trans_date, cost=cost_of_buy)

            return redirect("/")

        else:
            curr_quantity = db.execute("SELECT amount FROM stocks WHERE user_id = :user_id and symbol = :symbol", user_id=session["user_id"], symbol=stock['symbol'])
            new_quantity = curr_quantity[0]["amount"] + int(quantity)
            db.execute("UPDATE stocks SET amount = :amount WHERE user_id = :user_id and symbol = :symbol", amount=new_quantity, user_id=session["user_id"], symbol=stock['symbol'])
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=new_cash, id=session["user_id"])
            trans_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute("INSERT INTO transactions (user_id, symbol, amount, datetime, cost) VALUES (:user_id, :symbol, :amount, :datetime, :cost)", user_id=session["user_id"], symbol=stock['symbol'], amount=quantity, datetime=trans_date, cost=cost_of_buy)

            return redirect("/")



    else:
        return render_template("buy.html")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT * FROM transactions WHERE user_id = :user_id", user_id=session["user_id"])


    for row in rows:
        row["price"] = usd(row["cost"])

    return render_template("history.html", rows=rows)


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
    #store users stock prices to change color later based on increase or decrease (probably gonna need sql)
    rows = db.execute("SELECT symbol FROM stocks WHERE user_id = :user_id", user_id=session["user_id"])
    
    for row in rows:
        stock = lookup(row["symbol"])
        cost = stock['price']
        
        #MUST MAKE AN IF ELSE STATEMENT SO THAT WE DONT CREATE DUPLICATES IN OUR SQL TABLE 
        curr_stock = db.execute("SELECT * FROM prices WHERE user_id = :user_id and symbol = :symbol ", user_id=session["user_id"], symbol=row["symbol"])
        
        if not curr_stock:
            db.execute("INSERT INTO prices (user_id, symbol, price) VALUES (:user_id, :symbol, :price)", user_id=session["user_id"], symbol=row["symbol"], price=cost)
        else:
            db.execute("UPDATE prices SET price = :price WHERE user_id = :user_id and symbol = :symbol", price=cost, user_id=session["user_id"], symbol=row["symbol"])
            
    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""


    if request.method == "GET":
        return render_template("quote.html")

    elif request.method == "POST":
        stock = lookup(request.form.get("symbol"))
        if stock != None:
            company = stock['name']
            price = usd(stock['price'])
            symbol = stock['symbol']

        if not request.form.get("symbol"):
            return apology("enter stock symbol")
        elif stock == None:
            return apology("enter valid stock symbol")
        else:
            return render_template("quoted.html", company=company, price=price, symbol=symbol)



@app.route("/register", methods=["GET", "POST"])
def register():

    """Register user"""
    name = db.execute("SELECT username FROM users WHERE username = :username", username=request.form.get("username"))
    pass1 = request.form.get("password1")
    pass2 = request.form.get("password2")
    valid_password = False
    nam = request.form.get("username")

    if not name:
        check_name = 0
    else:
        check_name = name[0]["username"]

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must create username")

        elif request.form.get("username") == check_name:
            return apology("Username already exists")

        elif not pass1 or not pass2:
            return apology("must type password twice")

        elif pass1 != pass2:
            return apology("passwords must match")

        else:
            valid_password = True

        if valid_password == True:
            hashed_password = generate_password_hash(pass1)
            db.execute("INSERT INTO users (username, hash) VALUES (:username , :hash)", username=nam, hash=hashed_password)

            return redirect("/")



    if request.method == "GET":
        return render_template("register.html", name=name)


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    rows = db.execute("SELECT symbol FROM stocks WHERE user_id = :user_id", user_id=session["user_id"])

    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("must select stock")

        elif not request.form.get("shares"):
            return apology("input for shares to sell required")

        m = db.execute("SELECT amount FROM stocks WHERE symbol = :symbol and user_id = :user_id", symbol=request.form.get("symbol"), user_id=session["user_id"])
        max_sell = int(m[0]["amount"])
        request_sell = int(request.form.get("shares"))

        if request_sell > max_sell:
            return apology("insufficient shares")

        else:
            c = db.execute("SELECT cash FROM users WHERE id = :id", id=session["user_id"])
            cash = c[0]["cash"]
            symb = request.form.get("symbol")
            stock = lookup(symb)
            rebalance = stock['price'] * request_sell
            new_cash = cash + rebalance
            new_amount = max_sell - request_sell
            lose_stock = -request_sell


            db.execute("UPDATE stocks SET amount = :amount WHERE user_id = :user_id and symbol = :symbol", amount=new_amount, user_id=session["user_id"], symbol=symb)
            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=new_cash, id=session["user_id"])
            trans_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute("INSERT INTO transactions (user_id, symbol, amount, datetime, cost) VALUES (:user_id, :symbol, :amount, :datetime, :cost)", user_id=session["user_id"], symbol=symb, amount=lose_stock, datetime=trans_date, cost=rebalance)

            return redirect("/")

    else:
        return render_template("sell.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
